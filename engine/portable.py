"""Portable filesystem contracts. No scheduler, provider or assistant dependency."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import uuid


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Symlink output refused")
    payload = data if isinstance(data, bytes) else (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    temp = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        temp.write_bytes(payload)
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def child(root, name):
    """Reject archive/metadata paths and symlink ancestors before filesystem use."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("Invalid relative path")
    parts = PurePosixPath(name)
    if parts.is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("Unsafe relative path")
    root = Path(root).resolve()
    current = root
    for part in parts.parts:
        reserved = {"CON", "PRN", "AUX", "NUL", *["COM" + str(i) for i in range(1, 10)], *["LPT" + str(i) for i in range(1, 10)]}
        if part.endswith((".", " ")) or part.split(".")[0].upper() in reserved:
            raise ValueError("Nonportable reserved path")
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Symlink/junction path refused")
    if not current.resolve().is_relative_to(root):
        raise ValueError("Path escapes root")
    return current


def desktop_file(root, interpreter):
    """Freedesktop Exec quoting, not shell quoting; no command substitution."""
    args = [str(interpreter), str(Path(root) / "beyin.py"), "update"]
    if "=" in args[0] or any("\n" in a or "\r" in a for a in args):
        raise ValueError("Unsupported desktop launcher path")
    encoded = []
    for arg in args:
        arg = arg.replace("\\", "\\\\")
        for char in ('"', '`', '$'):
            arg = arg.replace(char, "\\" + char)
        # General Desktop Entry string escapes are decoded before Exec quoting.
        encoded.append('"' + arg.replace("\\", "\\\\").replace("%", "%%") + '"')
    return ("[Desktop Entry]\nType=Application\nName=Update SourceNest\nTerminal=true\nExec=" + " ".join(encoded) + "\n").encode()


def default_state(root, platform=None):
    platform = platform or sys.platform
    if os.environ.get("SOURCENEST_STATE_HOME"):
        base = Path(os.environ["SOURCENEST_STATE_HOME"])
    elif platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "SourceNest"
    elif platform == "darwin":
        base = Path.home() / "Library/Application Support/SourceNest"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "sourcenest"
    return base / sha(str(Path(root).resolve()).encode())[:24]


def validate_state(root, state):
    state = Path(state)
    if not state.is_absolute():
        raise ValueError("State path must be absolute")
    state = state.resolve()
    if state.is_relative_to(Path(root).resolve()):
        raise ValueError("Runtime state must be outside the vault")
    if any(p.casefold() in {"onedrive", "dropbox", "mobile documents", "icloud drive"} or p.casefold().startswith("onedrive - ") for p in state.parts):
        raise ValueError("Runtime state must not be in a cloud-sync folder")
    for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(name) and state.is_relative_to(Path(os.environ[name]).resolve()):
            raise ValueError("Runtime state must not be cloud-synced")
    return state


def state_dir(root):
    pointer = read(Path(root) / ".sourcenest-runtime.json", None)
    return validate_state(root, pointer["state"]) if pointer is not None else Path(root) / ".state"


def migrate_state(root, destination):
    """Copy and verify runtime state under the existing worker lock; retain old files."""
    import beyin
    root = Path(root).resolve()
    destination = validate_state(root, destination)
    previous = state_dir(root)
    if previous.resolve() == destination:
        return {"status": "noop", "state": str(destination)}
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Destination state must be empty")
    with beyin.lock(previous / "worker.lock") as held:
        if not held:
            raise ValueError("Worker busy; stop before state migration")
        destination.mkdir(parents=True, exist_ok=True)
        for source in previous.rglob("*"):
            if source.is_symlink():
                raise ValueError("Symlink in legacy state")
            if not source.is_file() or source.name.endswith(".lock") or source.name == "installation.json":
                continue
            relative = source.relative_to(previous).as_posix()
            target = child(destination, relative)
            data = source.read_bytes()
            write(target, data)
            if sha(target.read_bytes()) != sha(data):
                raise ValueError("State copy verification failed")
        write(root / ".sourcenest-runtime.json", {"schema_version": 1, "state": str(destination)})
    return {"status": "migrated", "state": str(destination), "legacy_files": "retained"}
