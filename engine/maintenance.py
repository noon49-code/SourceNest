"""SourceNest's independent verified package updater and recoverable transactions."""
from __future__ import annotations
import base64
import io
import urllib.error
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
from portable import desktop_file
import urllib.request
import zipfile
from portable import child, read, sha, state_dir, write

REPOSITORY = "noon49-code/SourceNest"
MAX_PACKAGE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
SEMVER = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def version(value):
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError("Stable semantic version required")
    return tuple(map(int, match.groups()))


def managed(name):
    if name in {"beyin.py", ".sourcenest-version", "Beyni Guncelle.cmd", "Beyni Güncelle.command", "Beyni Güncelle.sh", "Beyni Güncelle.desktop"}:
        return True
    if name.startswith("engine/") and len(name.split("/")) == 2:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+\.(py|cmd|ps1|sh)", name.split("/")[1]))
    return bool(re.fullmatch(r"(?:\.agents/skills|\.kiro/skills)/sourcenest(?:-doctor|-update)?/SKILL\.md", name)) or name.startswith(".sourcenest/adapters/") and name.endswith((".py", ".js", ".ts", ".json", ".yaml"))


def fetch(url, maximum=MAX_PACKAGE):
    if not url.startswith("https://"):
        raise ValueError("Release downloads require HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": "SourceNest-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("Insecure release redirect")
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Package download exceeds size limit")
    return data


def latest_release(transport=fetch, fallback=None):
    try:
        release = json.loads(transport(f"https://api.github.com/repos/{REPOSITORY}/releases/latest"))
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 429):
            raise
        if fallback is None:
            request = urllib.request.Request(f"https://github.com/{REPOSITORY}/releases/latest", headers={"User-Agent": "SourceNest-updater"})
            with urllib.request.urlopen(request, timeout=15) as response:
                resolved = response.geturl()
        else:
            resolved = fallback()
        prefix = f"https://github.com/{REPOSITORY}/releases/tag/"
        if not resolved.startswith(prefix):
            raise ValueError("Latest stable redirect unavailable")
        tag = resolved[len(prefix):]
        version(tag)
        filename = "SourceNest-" + tag.removeprefix("v") + ".zip"
        return {"version": tag.removeprefix("v"), "package_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}", "checksum_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}.sha256"}
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Latest release is not stable")
    tag = release["tag_name"]
    version(tag)
    filename = "SourceNest-" + tag.removeprefix("v") + ".zip"
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    try:
        urls = [assets[filename], assets[filename + ".sha256"]]
    except KeyError:
        raise ValueError("Stable release has no verified SourceNest package assets") from None
    prefix = f"https://github.com/{REPOSITORY}/releases/download/{tag}/"
    if any(not url.startswith(prefix) for url in urls):
        raise ValueError("Release asset is outside the official repository")
    return {"version": tag.removeprefix("v"), "package_url": urls[0], "checksum_url": urls[1]}


def download_release(destination, transport=fetch):
    release = latest_release(transport)
    data = transport(release["package_url"])
    checksum = transport(release["checksum_url"]).decode("ascii").split()[0]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum) or sha(data) != checksum.lower():
        raise ValueError("Release SHA-256 mismatch")
    destination = Path(destination)
    write(destination, data)
    write(Path(str(destination) + ".sha256"), (checksum + "\n").encode())
    return release


def package_files(package, checksum=None):
    """Validate before reading members; no extraction and no downloaded code execution."""
    package = Path(package)
    if package.stat().st_size > MAX_PACKAGE:
        raise ValueError("Package too large")
    package_data = package.read_bytes()
    checksum_path = Path(checksum) if checksum else Path(str(package) + ".sha256")
    expected = checksum_path.read_text(encoding="ascii").split()[0]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected) or sha(package_data) != expected.lower():
        raise ValueError("Package SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(package_data)) as archive:
        names, total = set(), 0
        for member in archive.infolist():
            name = member.filename.rstrip("/")
            child(Path(tempfile.gettempdir()) / "sourcenest-validation", name)
            if name.casefold() in names:
                raise ValueError("Duplicate package member")
            names.add(name.casefold())
            if stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                raise ValueError("Symlink or encrypted archive member")
            total += member.file_size
            if total > MAX_EXPANDED:
                raise ValueError("Expanded package exceeds limit")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("product") != "SourceNest" or manifest.get("schema_version") != 1:
            raise ValueError("Wrong package manifest")
        version(manifest["version"])
        files = manifest.get("files")
        if not isinstance(files, dict) or not {"engine/beyin.py", "beyin.py", ".sourcenest-version"}.issubset(files):
            raise ValueError("Incomplete package")
        payload = {}
        for name, checksum in files.items():
            if not managed(name):
                raise ValueError("Package attempts to manage user data")
            data = archive.read(name)
            if sha(data) != checksum:
                raise ValueError("Managed file checksum mismatch")
            payload[name] = data
        metadata = manifest.get("metadata_files", {})
        if not isinstance(metadata, dict) or not set(metadata).issubset({"LICENSE", "CREDITS.md"}):
            raise ValueError("Invalid package metadata")
        for name, checksum in metadata.items():
            if sha(archive.read(name)) != checksum:
                raise ValueError("Package metadata checksum mismatch")
        actual = {i.filename for i in archive.infolist() if not i.is_dir()}
        if actual != set(files) | set(metadata) | {"manifest.json"}:
            raise ValueError("Unlisted package files")
        if payload[".sourcenest-version"].decode().strip() != manifest["version"]:
            raise ValueError("Package version marker mismatch")
    return manifest, payload


def _transaction(root):
    return state_dir(root) / "maintenance.json"


def _encoded(data):
    return base64.b64encode(data).decode("ascii") if data is not None else None


def _decoded(data):
    return base64.b64decode(data, validate=True) if data is not None else None


def _installed_version(root):
    source = (root / "engine/beyin.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION = ["\']([^"\']+)', source)
    if not match:
        raise ValueError("Installed engine has no version marker")
    return match.group(1)


def update(root, package, checksum=None, check=False, allow_downgrade=False, reviewed_hashes=None):
    import beyin
    root = Path(root).resolve()
    manifest, payload = package_files(package, checksum)
    platform_suffix = ".cmd" if sys.platform == "win32" else ".command" if sys.platform == "darwin" else ".sh"
    payload = {n: d for n, d in payload.items() if not n.startswith("Beyni") or n.endswith(platform_suffix) or sys.platform.startswith("linux") and n.endswith(".desktop")}
    if sys.platform.startswith("linux") and "Beyni Güncelle.desktop" in payload:
        payload["Beyni Güncelle.desktop"] = desktop_file(root, sys.executable)
    with beyin.lock(state_dir(root) / "worker.lock") as held:
        if not held:
            raise ValueError("Worker busy")
        journal = read(_transaction(root), {})
        if journal and journal.get("status") in ("prepared", "applying", "recovering"):
            raise ValueError("Interrupted maintenance; run recover first")
        current = (root / ".sourcenest-version").read_text().strip() if (root / ".sourcenest-version").exists() else _installed_version(root)
        if version(manifest["version"]) < version(current) and not allow_downgrade:
            raise ValueError("Downgrade refused; use rollback")
        baseline = read(root / ".sourcenest-managed.json", {})
        legacy = read(root / ".state/installation.json", {}).get("managed_engine_sha256", {})
        expected = dict(legacy, **baseline)
        if reviewed_hashes:
            if any(name not in payload or not re.fullmatch(r"[a-f0-9]{64}", digest)
                   for name, digest in reviewed_hashes.items()):
                raise ValueError("Invalid reviewed managed-file hashes")
            expected.update(reviewed_hashes)
        conflicts, entries = [], []
        for name, after in payload.items():
            path = child(root, name)
            before = path.read_bytes() if path.exists() else None
            if before is not None and before != after and sha(before) != expected.get(name):
                conflicts.append(name)
            entries.append({"path": name, "before": _encoded(before), "after": _encoded(after), "before_sha256": sha(before) if before is not None else None, "after_sha256": sha(after), "before_mode": path.stat().st_mode & 0o777 if before is not None else None})
        if conflicts:
            if check:
                return {"status": "conflicts", "conflicts": conflicts, "version": manifest["version"]}
            raise ValueError("Managed file conflict: " + ", ".join(conflicts))
        changed = [e["path"] for e in entries if e["before"] != e["after"]]
        if check or not changed:
            return {"status": "available" if changed else "noop", "version": manifest["version"], "changed_files": changed}
        metadata = child(root, ".sourcenest-managed.json")
        hashes = dict(baseline, **{n: sha(d) for n, d in payload.items()})
        entries.append({"path": ".sourcenest-managed.json", "before": _encoded(metadata.read_bytes() if metadata.exists() else None),
                        "after": _encoded((json.dumps(hashes, indent=2) + "\n").encode()), "before_sha256": sha(metadata.read_bytes()) if metadata.exists() else None, "after_sha256": sha((json.dumps(hashes, indent=2) + "\n").encode()), "before_mode": metadata.stat().st_mode & 0o777 if metadata.exists() else None})
        transaction = {"schema_version": 1, "status": "prepared", "version": manifest["version"], "entries": entries}
        write(_transaction(root), transaction)
        transaction["status"] = "applying"
        write(_transaction(root), transaction)
        for entry in entries:
            target = child(root, entry["path"])
            write(target, _decoded(entry["after"]))
            if target.suffix in (".sh", ".command", ".desktop"):
                target.chmod(0o700)
        transaction["status"] = "committed"
        write(_transaction(root), transaction)
    return {"status": "updated", "version": manifest["version"], "changed_files": changed}


def restore(root, recover=False):
    import beyin
    root = Path(root).resolve()
    with beyin.lock(state_dir(root) / "worker.lock") as held:
        if not held:
            raise ValueError("Worker busy")
        path = _transaction(root)
        journal = read(path, {})
        statuses = {"prepared", "applying", "recovering"} if recover else {"committed"}
        if journal.get("status") not in statuses:
            return {"status": "noop", "reason": "no_interrupted_transaction" if recover else "no_committed_update"}
        planned, seen = [], set()
        for entry in journal["entries"]:
            name = entry["path"]
            if name in seen or not (managed(name) or name == ".sourcenest-managed.json"):
                raise ValueError("Invalid maintenance journal path")
            seen.add(name)
            target = child(root, name)
            before, after = _decoded(entry["before"]), _decoded(entry["after"])
            if (sha(before) if before is not None else None) != entry.get("before_sha256") or sha(after) != entry.get("after_sha256"):
                raise ValueError("Maintenance backup checksum mismatch")
            current = target.read_bytes() if target.exists() else None
            if current not in (before, after):
                raise ValueError("Recovery conflict: later user edit " + name)
            planned.append((target, before, entry.get("before_mode")))
        journal["status"] = "recovering"
        write(path, journal)
        for target, before, mode in planned:
            if before is None:
                target.unlink(missing_ok=True)
            else:
                write(target, before)
                if mode is not None:
                    target.chmod(mode)
        journal["status"] = "recovered" if recover else "rolled_back"
        write(path, journal)
    return {"status": journal["status"], "files": len(planned)}
