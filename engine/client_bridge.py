"""Bounded native-client stdin bridge. Source text never enters argv."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def run(root, client, event, payload):
    if not isinstance(payload, dict):
        return ""
    payload = dict(payload)
    payload["hook_event_name"] = {"PreInvocation": "UserPromptSubmit"}.get(event, event)
    if not payload.get("prompt") and client == "kiro":
        payload["prompt"] = os.environ.get("USER_PROMPT", "")
    payload.setdefault("cwd", os.getcwd())
    payload["client"] = client
    try:
        result = subprocess.run([sys.executable, str(Path(root) / "engine/beyin.py"), "--root", str(root), "hook", "--adapter", "normalized"],
                                input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True, timeout=12,
                                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        response = json.loads(result.stdout) if result.returncode == 0 else {}
        return response.get("hookSpecificOutput", {}).get("additionalContext", "")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--client", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--plain", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(sys.stdin.read(1000000).lstrip("\ufeff") or "{}")
    except ValueError:
        payload = {}
    text = run(args.root, args.client, args.event, payload)
    if args.plain:
        print(text)
    else:
        print(json.dumps({"hookSpecificOutput": {"additionalContext": text}}))


if __name__ == "__main__":
    main()
