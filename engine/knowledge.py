"""Human-authored Markdown sources, local lookup, and explicit identity setup."""
from __future__ import annotations
import json
from pathlib import Path
import re
import time
import unicodedata
from portable import child, read, sha, state_dir, write

MARKER = "<!-- sourcenest: "


def project_base(root, project):
    import beyin
    beyin.get_project(root, project)
    return beyin.safe_project(root, project)


def slug(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:70]
    if not value:
        raise ValueError("A nonempty ASCII slug is required")
    return value


def create(root, data):
    root = Path(root).resolve()
    import beyin
    if not isinstance(data, dict) or set(data) - {"project", "title", "body", "slug", "folder", "visibility", "remote_allowed", "sensitivity", "aliases"}:
        raise ValueError("Unknown note fields")
    project = data.get("project")
    base = project_base(root, project)
    if any(not isinstance(data.get(k), str) or not data[k].strip() for k in ("title", "body")):
        raise ValueError("Note title and body are required")
    if len(data["title"]) > 160 or len(data["body"]) > 100000:
        raise ValueError("Note exceeds size limit")
    folder = data.get("folder", "notes")
    if folder not in ("notes", "knowledge"):
        raise ValueError("Notes belong in notes/ or knowledge/")
    visibility = data.get("visibility", "private")
    remote = data.get("remote_allowed", False)
    sensitivity = data.get("sensitivity", "normal")
    aliases = data.get("aliases", [])
    if visibility not in ("private", "internal", "public") or type(remote) is not bool or sensitivity not in ("normal", "sensitive"):
        raise ValueError("Invalid note privacy metadata")
    if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(a, str) or len(a) > 100 for a in aliases):
        raise ValueError("Invalid note aliases")
    name = slug(data.get("slug") or data["title"])
    path = child(base, f"{folder}/{name}.md")
    metadata = {"project": project, "title": data["title"], "visibility": visibility,
                "remote_allowed": remote, "sensitivity": sensitivity, "aliases": aliases}
    text = MARKER + json.dumps(metadata, ensure_ascii=False) + " -->\n\n# " + data["title"] + "\n\n" + data["body"].strip() + "\n"
    with beyin.lock(state_dir(root) / "worker.lock") as held:
        if not held:
            raise ValueError("Worker busy; retry note-create")
        if path.exists():
            if path.read_text(encoding="utf-8") != text:
                raise ValueError("Note already exists; refusing to overwrite human source")
        else:
            write(path, text.encode())
    return {"created": str(path.relative_to(root)), "source_sha256": sha(path.read_bytes()), "model_calls": 0}


def sources(root, project):
    root = Path(root).resolve()
    base = project_base(root, project)
    found = []
    for folder in ("notes", "knowledge"):
        directory = base / folder
        if directory.is_symlink():
            raise ValueError("Symlink notes directory")
        for path in sorted(directory.glob("*.md")):
            child(base, path.relative_to(base).as_posix())
            if path.stat().st_size > 200000:
                continue
            data = path.read_bytes()
            text = data.decode("utf-8-sig")
            meta = {}
            if text.startswith(MARKER):
                first, _, text = text.partition("\n")
                meta = json.loads(first[len(MARKER):].removesuffix(" -->"))
                if meta.get("project") != project:
                    continue
            found.append({"id": sha(path.relative_to(root).as_posix().encode())[:24],
                          "project": project, "source": path.relative_to(root).as_posix(),
                          "source_sha256": sha(data), "title": meta.get("title", path.stem),
                          "body": text, "visibility": meta.get("visibility", "private"),
                          "remote_allowed": meta.get("remote_allowed", False),
                          "sensitivity": meta.get("sensitivity", "normal"), "aliases": meta.get("aliases", [])})
    return found


def lookup(root, project, query="", limit=8):
    terms = set(re.findall(r"\w+", query.casefold()))
    ranked = []
    for source in sources(root, project):
        content = " ".join([source["title"], source["body"], *source["aliases"]]).casefold()
        score = sum(term in content for term in terms)
        if terms and not score:
            continue
        ranked.append((score, source))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["source"]))
    return [source for _, source in ranked[:max(1, min(32, limit))]]


def sync(root, project=None):
    import beyin
    projects = [project] if project else [p["id"] for p in read(root / "projects.json")["projects"]]
    index = {p: [{k: v for k, v in source.items() if k != "body"} for source in sources(root, p)] for p in projects}
    with beyin.lock(state_dir(root) / "worker.lock") as held:
        if not held:
            raise ValueError("Worker busy; retry sync")
        write(state_dir(root) / "notes-index.json", index)
        counts = {p: beyin.rebuild(root, p) for p in projects}
    return {"synced": counts, "notes": sum(map(len, index.values())), "model_calls": 0}


def companion(root, data=None):
    root = Path(root).resolve()
    candidates = [p for name in ("Core.md", "Soul.md") for p in root.rglob(name) if not any(part in (".backups", ".git") for part in p.parts)]
    target = root / "companion/Core.md"
    if candidates and (len(candidates) != 1 or candidates[0] != target):
        return {"status": "needs_attention", "reason": "existing_identity_sources", "candidates": [p.relative_to(root).as_posix() for p in candidates]}
    if data is not None:
        if not isinstance(data, dict) or set(data) - {"name", "address_as", "preferences"} or any(not isinstance(v, str) or len(v) > 3000 for v in data.values()):
            raise ValueError("Identity accepts only name, address_as and preferences text")
        target = child(root, "companion/Core.md")
        if target.exists():
            raise ValueError("Existing identity is human-owned; edit it explicitly")
        text = "# Companion\n\n" + "\n\n".join(f"## {key}\n\n{value}" for key, value in data.items()) + "\n"
        write(target, text.encode())
    return {"status": "ready" if target.exists() else "not_configured", "source": "companion/Core.md" if target.exists() else None,
            "questions": [] if target.exists() else ["Sana nasıl hitap edelim?", "Kalıcı olarak hatırlanmasını istediğin çalışma tercihlerin neler?", "Hatırlanmamasını istediğin bilgiler var mı?"]}


def record_delivery(root, project, session, records):
    if not session or not isinstance(session, str):
        return
    import beyin
    path = state_dir(root) / "delivery-receipts.json"
    with beyin.lock(path.with_suffix(".lock"), blocking=True) as held:
        if held:
            receipts = read(path, [])
            receipts.append({"session": sha(session.encode()), "project": project, "at": time.time(),
                             "sources": [{"id": r["id"], "sha256": r["source_sha256"]} for r in records]})
            write(path, receipts[-500:])


def verify_session(root, project, record_id):
    source = next((r for r in sources(root, project) if r["id"] == record_id), None)
    if not source:
        raise ValueError("Unknown source")
    sessions = {r["session"] for r in read(state_dir(root) / "delivery-receipts.json", [])
                if r["project"] == project and any(s["id"] == record_id and s["sha256"] == source["source_sha256"] for s in r["sources"])}
    return {"verified": len(sessions) >= 2, "distinct_delivered_sessions": len(sessions), "source": source["source"],
            "next_step": "Ask for this information in a new assistant session" if len(sessions) < 2 else "Hook delivery recorded; verify the answer against this source"}
