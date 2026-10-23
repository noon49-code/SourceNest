"""Hermes callback bridge; imported only by the explicitly enabled Hermes plugin."""
import os
from client_bridge import run


def register(ctx, root):
    sessions = set()
    def before(**kw):
        session = kw.get("session_id")
        if not session or kw.get("parent_session_id"):
            return None
        event = "UserPromptSubmit" if session in sessions else "SessionStart"
        sessions.add(session)
        text = run(root, "hermes", event, {"session_id": session, "cwd": kw.get("cwd") or os.getcwd(), "prompt": kw.get("prompt", "")})
        return {"context": text} if text else None
    def finalize(**kw):
        session = kw.get("session_id")
        if session in sessions:
            run(root, "hermes", "SessionEnd", {"session_id": session, "cwd": kw.get("cwd") or os.getcwd()})
            sessions.discard(session)
    ctx.register_hook("pre_llm_call", before)
    ctx.register_hook("on_session_finalize", finalize)
