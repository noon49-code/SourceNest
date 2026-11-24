"""Regressions for portable handoffs, retrieval, privacy and the loopback UI."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode, urlsplit

import beyin
import knowledge
import local_web
import vault_tools
import workflow
from portable import write


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        write(self.root / "projects.json", {"projects": [{"id": "demo", "name": "Demo"},
                                                       {"id": "other", "name": "Other"}]})
        self.source = "notes/orchard.md"
        self.saved = knowledge.create(self.root, {"project": "demo", "title": "Orchard",
            "body": ("background filler " * 200) + "The orchard gate is painted violet."})

    def request(self, action, details):
        return workflow.operate(self.root, "demo", action, details)

    def test_passage_budget_and_session_dedup(self):
        cases = [{"query": "violet orchard", "source": self.source, "expected": "painted violet"}]
        self.assertTrue(vault_tools.selftest(self.root, "demo", cases, 3, 160)["ok"])
        matches = knowledge.lookup(self.root, "demo", "violet", 3, 160)
        self.assertEqual(knowledge.novel(self.root, "demo", "codex", "first", matches), matches)
        self.assertEqual(knowledge.novel(self.root, "demo", "codex", "first", matches), [])
        self.assertEqual(knowledge.novel(self.root, "demo", "pi", "first", matches), matches)
        knowledge.reset_deliveries(self.root, "codex", "first")
        self.assertEqual(knowledge.novel(self.root, "demo", "codex", "first", matches), matches)

    def test_feedback_is_scoped_to_the_current_revision(self):
        note = workflow.read_note(self.root, "demo", self.source)
        details = {"source": self.source, "sha256": note["sha256"]}
        self.request("feedback", dict(details, verdict="wrong", reason="Outdated"))
        self.assertFalse(knowledge.lookup(self.root, "demo", "violet"))
        workflow.edit_note(self.root, "demo", dict(details, body="# Orchard\nThe door is blue."))
        self.assertTrue(knowledge.lookup(self.root, "demo", "blue"))
        with self.assertRaisesRegex(ValueError, "changed"):
            workflow.edit_note(self.root, "demo", dict(details, body="Would overwrite"))
        history = workflow.note_history(self.root, "demo", self.source)
        self.assertEqual(history["previous"][0]["sha256"], note["sha256"])
        with self.assertRaises(ValueError):
            workflow.read_note(self.root, "other", "notes/../../demo/notes/orchard.md")

    def test_checkpoint_preview_and_replay_preserve_parallel_cards(self):
        data = {"session": "one", "title": "First", "outcome": "Inspected gate",
                "next_step": "Ask owner", "refs": [self.source], "threads": ["Paint"],
                "learning": "Check the gate color"}
        self.assertEqual(workflow.operate(self.root, "demo", "checkpoint", data, True)["status"], "preview")
        self.assertFalse(workflow.ledger_path(self.root, "demo").exists())
        self.request("checkpoint", data)
        self.request("checkpoint", dict(data, session="two"))
        self.assertEqual(self.request("checkpoint", data)["status"], "noop")
        self.request("checkpoint", dict(data, next_step="Test hinge"))
        state = workflow.ledger(self.root, "demo")
        self.assertEqual(len(state["checkpoints"]), 2)
        self.assertEqual(len(state["learning"]), 2)
        task = self.request("task-create", {"id": "gate", "title": "Review gate", "next_step": "Open gate"})["record"]
        self.request("task-update", {"id": task["id"], "revision": 1, "status": "done"})
        with self.assertRaisesRegex(ValueError, "revision"):
            self.request("task-update", {"id": task["id"], "revision": 1, "status": "cancelled"})

    def test_backfill_cannot_change_after_preview_or_enter_model_queue(self):
        export = self.root / "export.jsonl"
        export.write_text(json.dumps({"role": "user", "content": "Unique archived message"}) + "\n", encoding="utf-8")
        preview = vault_tools.backfill(self.root, "demo", export, "normalized")
        self.assertEqual(preview["messages"], 1)
        with self.assertRaisesRegex(ValueError, "preview"):
            vault_tools.backfill(self.root, "demo", export, "normalized", "wrong")
        result = vault_tools.backfill(self.root, "demo", export, "normalized", preview["sha256"])
        self.assertEqual(result["processing"], "local-only")
        self.assertFalse((self.root / ".queue").exists())
        self.assertTrue(knowledge.lookup(self.root, "demo", "archived"))
        self.assertFalse(beyin.hook_notes(self.root, "demo", "archived", "codex", "one"))

    def test_model_cutoff_fails_closed_for_missing_dates(self):
        project = {"model_processing_since": "2026-11-16T20:00:00Z"}
        self.assertFalse(beyin.model_processing_allowed(project, {"origin": {}, "messages": [{"timestamp": None}]}))
        self.assertFalse(beyin.model_processing_allowed(project, {"origin": {}, "messages": [
            {"timestamp": "2026-11-16T19:59:59Z"}, {"timestamp": "2026-11-16T20:01:00Z"}]}))
        self.assertTrue(beyin.model_processing_allowed(project, {"origin": {}, "messages": [
            {"timestamp": "2026-11-16T20:01:00Z"}]}))

    def test_web_cookie_origin_csrf_and_note_capture(self):
        server, link = local_web.make_server(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        self.addCleanup(connection.close)

        def request(method, url, headers=None, body=None):
            connection.request(method, url, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheader("Set-Cookie"), response.read().decode()

        self.assertEqual(request("GET", "/?project=demo")[0], 403)
        url = urlsplit(link)
        status, cookie, _ = request("GET", url.path + "?" + url.query)
        self.assertEqual(status, 303)
        self.assertEqual(request("GET", url.path + "?" + url.query)[0], 403)
        session = {"Cookie": cookie.split(";", 1)[0]}
        self.assertEqual(request("GET", "/?project=demo", dict(session, Host="example.org"))[0], 403)
        status, _, page = request("GET", "/?project=demo&q=violet", session)
        self.assertEqual(status, 200)
        self.assertIn("painted violet", page)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page)[1]
        headers = dict(session, **{"Content-Type": "application/x-www-form-urlencoded"})
        data = {"project": "demo", "title": "Local test", "body": "<script>private</script>"}
        self.assertEqual(request("POST", "/capture", headers, urlencode(data))[0], 403)
        self.assertEqual(request("POST", "/capture", headers, urlencode(dict(data, csrf=csrf)))[0], 303)
        _, _, result = request("GET", "/?project=demo&q=private", session)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)


if __name__ == "__main__":
    unittest.main()
