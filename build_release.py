"""Build the managed update archive and full source distribution, with SHA-256 files."""
from pathlib import Path
import argparse
import json
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import beyin
from portable import sha, write

PACKAGE = Path(__file__).resolve().parent


def payload_files():
    import install
    files = {name: (PACKAGE / name).read_bytes() for name in install.MANAGED_ENGINE}
    files["engine/__init__.py"] = (PACKAGE / "engine/__init__.py").read_bytes()
    files["beyin.py"] = (PACKAGE / "beyin.py").read_bytes()
    files[".sourcenest-version"] = (beyin.VERSION + "\n").encode()
    files["Beyni Guncelle.cmd"] = b'@echo off\r\ncall "%~dp0engine\\Beyin.cmd" update\r\nexit /b %ERRORLEVEL%\r\n'
    shortcut = b'#!/bin/sh\nset -eu\nROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nif [ -n "${SOURCENEST_PYTHON:-}" ]; then exec "$SOURCENEST_PYTHON" "$ROOT/beyin.py" update; fi\nif command -v python3 >/dev/null 2>&1; then exec python3 "$ROOT/beyin.py" update; fi\nexec python "$ROOT/beyin.py" update\n'
    files["Beyni Güncelle.command"] = shortcut
    files["Beyni Güncelle.sh"] = shortcut
    files["Beyni Güncelle.desktop"] = b"# SourceNest desktop launcher is rendered for the local installation\n"
    return files


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    files = payload_files()
    manifest = {"schema_version": 1, "product": "SourceNest", "version": beyin.VERSION, "files": {name: sha(data) for name, data in files.items()}, "metadata_files": {name: sha((PACKAGE / name).read_bytes()) for name in ("LICENSE", "CREDITS.md")}}
    path = destination / ("SourceNest-" + beyin.VERSION + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        for name in manifest["metadata_files"]:
            archive.write(PACKAGE / name, name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    write(Path(str(path) + ".sha256"), (sha(path.read_bytes()) + "  " + path.name + "\n").encode())
    # Fresh-install distribution: explicit source-file whitelist, never a working-tree archive.
    source = destination / ("SourceNest-" + beyin.VERSION + "-source.zip")
    names = ["setup.py", "install.py", "build_release.py", "beyin.py", "config.example.json", "projects.example.json", "vault.gitignore", "README.md", "README.tr.md", "PROFILE.md", "RULES.md", "LICENSE", "CREDITS.md", "PRIVACY.md", "setup.ps1", "setup.cmd", "CONTRIBUTING.md", "VALIDATION.md", "pyproject.toml"]
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(PACKAGE / name, name)
        for name, data in files.items():
            if name.startswith("engine/"):
                archive.writestr(name, data)
        for name in ("docs/integrations.md", "docs/avenox-v3-adaptation.md", "docs/v2-guide.md", "docs/architecture.svg", "tests/test_beyin.py", "tests/test_public_install.py", "tests/test_runtime.py", "tests/test_workflow.py", "docs/v2.1-guide.md", "docs/demo.svg", ".github/workflows/test.yml"):
            archive.write(PACKAGE / name, name)
    write(Path(str(source) + ".sha256"), (sha(source.read_bytes()) + "  " + source.name + "\n").encode())
    return {"package": str(path), "source": str(source), "version": beyin.VERSION}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output)))
