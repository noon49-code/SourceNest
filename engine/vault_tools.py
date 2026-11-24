"""Local project lint, retrieval checks and explicitly selected historical imports."""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import knowledge
import workflow
from portable import child, sha, state_dir

LINK = re.compile(r"!?(?:\[\[([^\]\r\n]{1,600})\]\]|\[[^\]\r\n]{0,600}\]\(([^)\r\n]{1,600})\))")
HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def heading_key(text):
    return re.sub(r"[^\w -]", "", text.strip().casefold()).replace(" ", "-")


def lint(root, project_id):
    project = workflow.project(root, project_id)
    base = child(root, "projects/" + project["id"])
    notes = knowledge.sources(root, project["id"], include_review=True)
    paths = {r["source"]: r for r in notes}
    incoming = set()
    findings = []
    for source, record in paths.items():
        body = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*", "", record["body"])
        for match in LINK.finditer(body):
            wiki, markdown = match.groups()
            target = unquote((wiki or markdown).split("|", 1)[0].strip().strip("<>"))
            if not target or urlsplit(target).scheme or target.startswith("//"):
                continue
            file, _, anchor = target.partition("#")
            current = root / source
            if not file:
                candidates = [current]
            elif wiki and "/" not in file:
                file = Path(file)
                candidates = [root / path for path in paths if Path(path).stem.casefold() == file.stem.casefold()]
            else:
                if wiki and not Path(file).suffix:
                    file += ".md"
                candidates = [(current.parent / file).resolve()]
                if wiki and not candidates[0].exists():
                    candidates = [(base / file).resolve()]
            candidates = [p for p in candidates if p.is_relative_to(base) and p.is_file()]
            if len(candidates) != 1:
                findings.append({"source": source, "target": target,
                                 "code": "ambiguous-link" if candidates else "broken-link"})
                continue
            dest = candidates[0].relative_to(root).as_posix()
            if dest != source:
                incoming.add(dest)
            if anchor and dest in paths and heading_key(anchor) not in {
                    heading_key(h) for h in HEADING.findall(paths[dest]["body"])}:
                findings.append({"source": source, "target": target, "code": "missing-heading"})
    return {"findings": findings, "orphans": sorted(set(paths) - incoming), "notes": len(paths)}


def triage(root, project_id):
    import beyin
    state = workflow.ledger(root, project_id)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    pending = [task for task in state["tasks"].values() if task["status"] not in workflow.TERMINAL]
    stale = [task["id"] for task in pending
             if (task.get("due") and task["due"] < today) or beyin._timestamp(task["updated_at"]) < cutoff]
    duplicates = {}
    for source in knowledge.sources(root, project_id, include_review=True):
        title = " ".join(knowledge.tokens(source["title"]))
        duplicates.setdefault(title, []).append(source["source"])
    inbox = [r["source"] for r in knowledge.sources(root, project_id)
             if Path(r["source"]).name.startswith("inbox-")]
    outcomes = {}
    for file in sorted((child(root, "projects/" + project_id) / "records").glob("*.json")):
        try:
            record = beyin.read_json(file)
            for item in record["items"]:
                if item["kind"] in ("decision", "correction"):
                    topic = " ".join(knowledge.tokens(item["topic"]))
                    if topic:
                        outcomes.setdefault(topic, []).append({"kind": item["kind"],
                            "source": file.relative_to(root).as_posix(),
                            "event_id": record["event_id"]})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    corrections = [rows[-12:] for rows in outcomes.values()
                   if {"decision", "correction"} <= {row["kind"] for row in rows}]
    return {"open_tasks": pending, "stale_tasks": stale, "inbox": inbox,
            "possible_revisions": corrections,
            "matching_titles": [paths for title, paths in duplicates.items() if title and len(paths) > 1],
            "feedback": state["feedback"], "learning_pending": sum(r["status"] == "pending" for r in state["learning"].values()),
            "recent": workflow.recap(root, project_id, 7), "links": lint(root, project_id)}


def selftest(root, project_id, cases, limit, budget):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("Provide 1–100 retrieval cases")
    results = []
    for number, case in enumerate(cases, 1):
        workflow.fields(case, "query source expected")
        query = workflow.clean(case.get("query"), "query", 1000)
        expected = case.get("expected")
        if not isinstance(expected, str) or not expected.strip():
            raise ValueError("Expected a source quotation")
        path = workflow.note_path(root, project_id, case.get("source")).relative_to(root).as_posix()
        results_for_query = knowledge.lookup(root, project_id, query, limit, budget)
        found = next((r for r in results_for_query if r["source"] == path), None)
        results.append({"case": number, "source": path, "status": "pass" if found and expected in found["body"] else
                        "excerpt-missing" if found else "source-not-retrieved"})
    return {"ok": all(r["status"] == "pass" for r in results), "results": results, "model_calls": 0}


def homepage(root, project_id, data, slug="project-home"):
    workflow.fields(data, "title sources")
    title = workflow.clean(data.get("title"), "title", 120).replace("\n", " ")
    references = workflow.refs(root, project_id, data.get("sources", []))
    if not references:
        raise ValueError("Select at least one existing project note")
    from urllib.parse import quote
    prefix = f"projects/{project_id}/"
    links = []
    for ref in references:
        relative = ref["source"].removeprefix(prefix)
        if relative == f"notes/{slug}.md":
            raise ValueError("The homepage cannot link itself")
        label = Path(relative).stem.replace("[", "").replace("]", "")
        links.append("- [" + label + "](../" + quote(relative, safe="/") + ")")
    return knowledge.create(root, {"project": project_id, "slug": slug,
                                  "title": title, "body": "\n".join(links)})


def backfill(root, project_id, filename, adapter, approved_sha=None):
    """Preview one chosen transcript and import its eligible visible messages locally."""
    import beyin
    project = workflow.project(root, project_id)
    if not filename.is_file() or filename.stat().st_size > 20_000_000:
        raise ValueError("Choose one JSONL transcript of at most 20 MB")
    raw = filename.read_bytes()
    digest = sha(raw)
    messages = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            message = beyin.message_from(json.loads(line), adapter)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"Malformed transcript entry on line {number}") from None
        if message:
            messages.append(message)
    if not messages:
        raise ValueError("No supported user/assistant messages in the selected export")
    report = {"status": "preview", "sha256": digest, "messages": len(messages),
              "project": project_id, "model_calls": 0}
    if approved_sha is None:
        return report
    if approved_sha != digest:
        raise ValueError("Transcript differs from its preview")
    # Archive explicit history as private, non-injected notes, outside the model queue.
    sections = []
    for index, message in enumerate(messages, 1):
        for offset in range(0, len(message["text"]), 14000):
            heading = f"Entry {index} ({message['role']})"
            stamp = beyin._timestamp(message["timestamp"])
            if stamp:
                heading += " " + stamp.isoformat()
            sections.append((heading, message["text"][offset:offset + 14000]))
    notes = []
    for index, (heading, body) in enumerate(sections, 1):
        result = knowledge.create(root, {"project": project_id,
            "slug": f"archive-{digest[:16]}-{index}", "title": heading,
            "body": body, "visibility": "private", "sensitivity": "sensitive"})
        notes.append(result["created"])
    return dict(report, status="imported", sources=notes, processing="local-only")


def devices(root, args):
    """Plan a notes-only phone arrangement without attaching any sync service."""
    from portable import read, write
    profile = state_dir(root) / "device-profile.json"
    if args.detect:
        return {"platform": sys.platform, "profile": read(profile, {"level": "solo"}),
                "state_outside_vault": not state_dir(root).is_relative_to(root)}
    if (args.level == "phone") != bool(args.phone_sync):
        raise ValueError("Choose a phone sync provider only with --level phone")
    result = {"level": args.level, "phone_sync": args.phone_sync,
              "sync_managed_by_sourcenest": False, "scope": "user-selected Markdown notes only"}
    if args.apply:
        from beyin import lock
        with lock(state_dir(root) / "worker.lock", blocking=True) as held:
            if not held:
                raise ValueError("Worker busy")
            write(profile, result)
    return dict(result, status="saved" if args.apply else "plan")


def dispatch(root, args):
    command = args.command
    project_id = workflow.project(root, args.project)["id"]
    if command == "note-read":
        return workflow.read_note(root, project_id, args.source)
    if command == "history":
        return workflow.note_history(root, project_id, args.source)
    if command == "backfill":
        return backfill(root, project_id, args.file, args.adapter, args.approve_sha)
    if command in {"tasks", "learn"}:
        return list(workflow.ledger(root, project_id)["tasks" if command == "tasks" else "learning"].values())
    if command == "recap":
        return workflow.recap(root, project_id, args.days)
    if command == "triage":
        return triage(root, project_id)
    if command == "lint":
        return lint(root, project_id)
    if command == "scheduled-check":
        from beyin import audit
        return {"sync": knowledge.sync(root, project_id), "audit": audit(root, project_id)}
    if command == "moc":
        notes = knowledge.sources(root, project_id)
        links = [r["source"] for r in notes if Path(r["source"]).name not in {"project-home.md", "map-of-content.md"}]
        return homepage(root, project_id, {"title": "Project note index", "sources": links[:20]}, slug="map-of-content")
    data = json.loads(args.file.read_text(encoding="utf-8-sig"))
    if command == "note-edit":
        return workflow.edit_note(root, project_id, data)
    if command == "selftest":
        return selftest(root, project_id, data, args.limit, args.budget)
    if command == "homepage-create":
        return homepage(root, project_id, data)
    if command == "capture":
        from local_web import capture
        return capture(root, project_id, data)
    return workflow.operate(root, project_id, command, data, args.dry_run)
