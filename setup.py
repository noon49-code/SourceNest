"""Cross-platform SourceNest setup. Preview by default, --apply to write."""
from pathlib import Path
import argparse
import json
import sys
import install
from portable import default_state, migrate_state, write, sha
import clients
import knowledge


def bootstrap(target):
    from build_release import payload_files
    from maintenance import managed
    files = payload_files()
    for name, data in files.items():
        if name.startswith("engine/"):
            continue
        if name.startswith("Beyni"):
            if sys.platform == "win32" and not name.endswith(".cmd"):
                continue
            if sys.platform == "darwin" and not name.endswith(".command"):
                continue
            if sys.platform not in ("win32", "darwin") and not name.endswith(".sh"):
                continue
        path = target / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError("Bootstrap conflict: " + name)
        write(path, data)
        if name.endswith((".sh", ".command")):
            path.chmod(0o700)
    if sys.platform.startswith("linux"):
        # Desktop launchers use an explicit working directory; never execute an unquoted vault path.
        from portable import child, desktop_file
        launcher = child(target, "Beyni Güncelle.desktop")
        desktop = desktop_file(target, sys.executable)
        if not launcher.exists():
            write(launcher, desktop)
            launcher.chmod(0o700)
    write(target / ".sourcenest-managed.json", {name: sha((target / name).read_bytes()) for name in files if managed(name) and (target / name).is_file()})


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--client", action="append", choices=clients.SUPPORTED, default=[])
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--project", help="Explicit project ID for the workspace")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required")
    target = args.vault.resolve()
    state = args.state or default_state(target)
    existing = target.exists()
    if target.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError("Choose a private vault outside the SourceNest source checkout")
    if (target / ".sourcenest-runtime.json").exists():
        from portable import state_dir
        current_state = state_dir(target)
        if args.state and args.state.resolve() != current_state.resolve():
            raise ValueError("Existing state is preserved; use state-migrate explicitly")
        state = current_state
    plan = {"operation": "upgrade" if existing else "install", "vault": str(target), "state": str(state), "clients": args.client,
            "workspace": str(args.workspace) if args.workspace else None, "trust": "Client trust is a manual step"}
    if not args.apply:
        if existing:
            plan["preflight"] = install.upgrade_plan(target)
        print(json.dumps(plan, indent=2))
        return
    if existing:
        import tempfile
        import maintenance
        from build_release import build
        with tempfile.TemporaryDirectory(prefix="sourcenest-setup-") as directory:
            package = build(Path(directory))["package"]
            maintenance.update(target, package)
    else:
        install.install(target, None, {"schema_version": 1, "projects": []})
        bootstrap(target)
    if not (target / ".sourcenest-runtime.json").exists():
        migrate_state(target, state)
    if args.workspace:
        # Registration is explicit through --workspace and keeps independent project storage.
        existing_project = install.beyin.project_for(target, args.workspace.resolve())
        identifier = args.project or (existing_project["id"] if existing_project else knowledge.slug(args.workspace.resolve().name) + "-" + sha(str(args.workspace.resolve()).encode())[:8])
        install.beyin.register(target, identifier, args.workspace.resolve(), args.workspace.name)
    report = clients.install(target, args.client, workspace=args.workspace)
    report["companion"] = knowledge.companion(target)
    report["next_step"] = "Review client hooks/workspace trust, create an authorized example note, sync, then retrieve it in a new session"
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
