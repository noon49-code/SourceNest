"""Project-scoped notes, handoffs and human decisions. All writes are explicit."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import knowledge
from portable import child, read, sha, state_dir, write


def project(root, name):
    import beyin
    projects = beyin.read_json(root / "projects.json")["projects"]
    exact = [p for p in projects if p["id"] == name]
    matches = exact or [p for p in projects if p.get("name", "").casefold() == name.casefold()]
    if len(matches) != 1:
        raise ValueError("Specify an unambiguous registered project ID")
    return matches[0]


def note_path(root, project_id, source):
    base = child(root, "projects/" + project_id)
    if not isinstance(source, str):
        raise ValueError("Expected a project-relative Markdown source")
    prefix = "projects/" + project_id + "/"
    source = source.removeprefix(prefix)
    if not source.startswith(("notes/", "knowledge/")) or not source.endswith(".md"):
        raise ValueError("Only project notes and knowledge files are supported")
    return child(base, source)


def read_note(root, project_id, source):
    project(root, project_id)
    path = note_path(root, project_id, source)
    if not path.is_file() or path.stat().st_size > 200000:
        raise ValueError("Missing or oversized note")
    raw = path.read_bytes()
    return {"source": path.relative_to(root).as_posix(), "sha256": sha(raw),
            "text": raw.decode("utf-8-sig")}


def clean(value, label, maximum=2000):
    import beyin
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Invalid " + label)
    return beyin.redact(value.strip())


def fields(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed.split()):
        raise ValueError("Unexpected request fields")


def ledger_path(root, project_id):
    return child(root, "projects/" + project_id + "/notes/.sourcenest-workflow.json")


def ledger(root, project_id):
    return read(ledger_path(root, project_id), {"schema": 1, "tasks": {}, "checkpoints": {},
                                               "learning": {}, "feedback": {}, "history": {}})


def refs(root, project_id, values):
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("Expected up to 20 project note references")
    result = []
    for source in values:
        note = read_note(root, project_id, source)
        result.append({key: note[key] for key in ("source", "sha256")})
    return result


def edit_note(root, project_id, data):
    import beyin
    fields(data, "source sha256 body")
    with beyin.lock(state_dir(root) / "worker.lock", blocking=True) as held:
        if not held:
            raise ValueError("Worker busy")
        old = read_note(root, project_id, data.get("source"))
        if old["sha256"] != data.get("sha256"):
            raise ValueError("Note changed since note-read; reload it")
        path = note_path(root, project_id, old["source"])
        raw = path.read_bytes()
        if sha(raw) != old["sha256"]:
            raise ValueError("Note changed during edit; reload it")
        body = data.get("body")
        if not isinstance(body, str) or not body.strip() or len(body) > 100000 or knowledge.MARKER in body:
            raise ValueError("Expected a Markdown body without a SourceNest metadata marker")
        first = raw.splitlines(keepends=True)[0] if raw else b""
        metadata = first if first.decode("utf-8-sig").startswith(knowledge.MARKER) else b""
        replacement = metadata + body.strip().encode("utf-8") + b"\n"
        if replacement == raw:
            return {"status": "noop", "source": old["source"], "sha256": old["sha256"]}
        history = child(root, "projects/" + project_id + "/notes/.sourcenest-revisions/" +
                        sha(old["source"].encode()) + "/" + old["sha256"] + ".md")
        if not history.exists():
            write(history, raw)
        if sha(path.read_bytes()) != old["sha256"]:
            raise ValueError("Note changed during edit; reload it")
        write(path, replacement)
        return {"status": "updated", "source": old["source"], "sha256": sha(replacement)}


def note_history(root, project_id, source):
    note = read_note(root, project_id, source)
    folder = child(root, "projects/" + project_id + "/notes/.sourcenest-revisions/" +
                   sha(note["source"].encode()))
    revisions = []
    for file in sorted(folder.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        snapshot = child(folder, file.name).read_bytes()
        if file.stem != sha(snapshot):
            raise ValueError("Corrupt note revision")
        revisions.append({"sha256": file.stem, "text": snapshot.decode("utf-8-sig")})
    return {"current": note, "previous": revisions}


TERMINAL = {"done", "cancelled"}
STATES = {"open", "blocked", *TERMINAL}


def operate(root, project_id, action, data, preview=False):
    """Validate a complete change before committing a single atomic project file."""
    import beyin
    project(root, project_id)
    with beyin.lock(state_dir(root) / "worker.lock", blocking=True) as held:
        if not held:
            raise ValueError("Worker busy")
        state = ledger(root, project_id)
        at = beyin.now()
        if action == "checkpoint":
            fields(data, "session title outcome next_step refs threads learning")
            session = sha(clean(data.get("session"), "session", 250).encode())[:24]
            outcome = clean(data.get("outcome"), "outcome", 3000)
            sources = refs(root, project_id, data.get("refs", []))
            threads = data.get("threads", [])
            if not isinstance(threads, list) or len(threads) > 20:
                raise ValueError("Expected up to 20 open threads")
            current = state["checkpoints"].get(session)
            record = {"id": session, "title": clean(data.get("title"), "title", 160),
                      "outcome": outcome, "next_step": clean(data.get("next_step"), "next step"),
                      "threads": [clean(t, "thread", 500) for t in threads],
                      "refs": sources, "updated_at": at}
            state["checkpoints"][session] = record
            if "learning" in data:
                if not sources:
                    raise ValueError("Learning candidates need an existing source note")
                observation = clean(data["learning"], "learning candidate")
                candidate = sha((session + observation).encode())[:24]
                state["learning"].setdefault(candidate, {"id": candidate, "text": observation,
                                                         "refs": sources, "status": "pending", "at": at})
                record["learning"] = candidate
            record["revision"] = (current or {}).get("revision", 0) + 1
            if current and {k: v for k, v in current.items() if k not in {"updated_at", "revision"}} == {k: v for k, v in record.items() if k not in {"updated_at", "revision"}}:
                return {"status": "noop", "record": current}
        elif action in {"task-create", "task-update"}:
            fields(data, "id title status next_step refs due revision")
            identifier = knowledge.slug(clean(data.get("id"), "task ID", 70))
            current = state["tasks"].get(identifier)
            if action == "task-create":
                if current:
                    raise ValueError("Task already exists")
                current = {"id": identifier, "revision": 0, "status": "open", "refs": []}
            elif not current or type(data.get("revision")) is not int or data["revision"] != current["revision"]:
                raise ValueError("Task revision changed; reload it before updating")
            record = dict(current)
            for key in ("title", "next_step"):
                if key in data or key not in record:
                    record[key] = clean(data.get(key), key)
            if "refs" in data:
                record["refs"] = refs(root, project_id, data["refs"])
            if data.get("status", record["status"]) not in STATES:
                raise ValueError("Use open, blocked, done or cancelled")
            record["status"] = data.get("status", record["status"])
            if "due" in data:
                record["due"] = dt.date.fromisoformat(data["due"]).isoformat() if data["due"] else None
            record.update(revision=current["revision"] + 1, updated_at=at)
            if current["revision"]:
                state["history"].setdefault(identifier, []).append(current)
            state["tasks"][identifier] = record
        elif action == "feedback":
            fields(data, "source verdict reason session sha256")
            source = read_note(root, project_id, data.get("source"))
            if source["sha256"] != data.get("sha256"):
                raise ValueError("Feedback refers to an outdated note revision")
            verdict = data.get("verdict")
            if verdict not in {"ok", "wrong", "stale"}:
                raise ValueError("Use ok, wrong or stale")
            record = {"source_sha256": source["sha256"], "verdict": verdict, "at": at,
                      "reason": clean(data.get("reason"), "feedback reason")}
            if "session" in data:
                record["session"] = sha(clean(data["session"], "session", 250).encode())[:24]
            state["feedback"][source["source"]] = record
        elif action == "learn-resolve":
            fields(data, "id status")
            candidate = state["learning"].get(data.get("id"))
            if not candidate or candidate["status"] != "pending" or data.get("status") not in {"accepted", "rejected"}:
                raise ValueError("An unresolved candidate and accepted/rejected status are required")
            record = dict(candidate, status=data["status"], resolved_at=at)
            state["learning"][candidate["id"]] = record
        else:
            raise ValueError("Unknown workflow action")
        if not preview:
            write(ledger_path(root, project_id), state)
    return {"status": "preview" if preview else "saved", "record": record, "model_calls": 0}


def recap(root, project_id, days):
    import beyin
    if not 1 <= days <= 365:
        raise ValueError("Days must be 1–365")
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    state = ledger(root, project_id)
    rows = list(state["checkpoints"].values())
    rows.extend(t for t in state["tasks"].values() if t["status"] in TERMINAL)
    return sorted((r for r in rows if beyin._timestamp(r["updated_at"]) >= cutoff),
                  key=lambda r: r["updated_at"], reverse=True)


def continuity(root, project_id):
    """Provide the last explicitly saved handoff for this project."""
    cards = ledger(root, project_id)["checkpoints"]
    return max(cards.values(), key=lambda r: r["updated_at"], default=None)


def workspaces(root):
    from beyin import read_json
    return [{"id": p["id"], "name": p.get("name", p["id"]),
             "workspace_count": len(p.get("paths", []))}
            for p in read_json(root / "projects.json")["projects"]]
