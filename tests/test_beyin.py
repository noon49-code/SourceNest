import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "engine"))
import beyin
sys.path.insert(0, str(PACKAGE))
import install


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beyin-test-")
        self.root = Path(self.temp.name) / "vault"
        self.root.mkdir()
        cfg = json.loads((PACKAGE / "config.example.json").read_text())
        cfg["auto_process"] = False
        cfg["git_checkpoints"] = False
        beyin.atomic(self.root / "config.json", cfg)
        self.project = {"id": "alpha", "name": "Alpha", "paths": [str(Path(self.temp.name) / "project-a")], "references": []}
        self.other = {"id": "beta", "name": "Beta", "paths": [str(Path(self.temp.name) / "project-b")], "references": []}
        beyin.atomic(self.root / "projects.json", {"schema_version": 1, "projects": [self.project, self.other]})
        self.transcript = Path(self.temp.name) / "session.jsonl"
        self.payload = {"session_id": "session-one", "transcript_path": str(self.transcript), "cwd": self.project["paths"][0]}

    def tearDown(self):
        self.temp.cleanup()

    def write_turns(self, texts, append=False):
        with self.transcript.open("a" if append else "w", encoding="utf-8", newline="\n") as stream:
            for i, (role, text) in enumerate(texts):
                record = {"type": "event_msg", "timestamp": f"2026-09-12T12:00:{i:02d}Z",
                          "payload": {"type": "user_message" if role == "user" else "agent_message", "message": text}}
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def event(self):
        self.write_turns([("user", "Özetleyici Luna olsun."), ("assistant", "Terra da denenebilir.")])
        beyin.capture(self.root, self.project, self.payload, "codex")
        return beyin.read_json(next((self.root / "projects/alpha/raw/events").glob("*.json")))

    def summary(self, event, assistant=False):
        m = event["messages"][1 if assistant else 0]
        return {"summary": "Özetleyici seçimi konuşuldu.", "items": [{"kind": "decision", "text": m["text"],
                "topic": "Özetleyici seçimi", "evidence_ids": [m["id"]], "evidence_quote": m["text"], "uncertain": False}]}

    def test_replayed_hook_and_later_append(self):
        self.event()
        self.assertEqual(beyin.capture(self.root, self.project, self.payload, "codex"), 0)
        self.assertEqual(len(list((self.root / ".queue").glob("*.json"))), 1)
        self.write_turns([("user", "Karar değişti; sağlayıcı seçilebilir olsun.")], append=True)
        self.assertEqual(beyin.capture(self.root, self.project, self.payload, "codex"), 1)
        self.assertEqual(len(list((self.root / ".queue").glob("*.json"))), 2)

    def test_incomplete_tail_is_retried(self):
        self.write_turns([("user", "Birinci kayıt.")])
        line = json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "İkinci kayıt."}})
        with self.transcript.open("a", encoding="utf-8") as f:
            f.write(line[:20])
        beyin.capture(self.root, self.project, self.payload, "codex")
        with self.transcript.open("a", encoding="utf-8") as f:
            f.write(line[20:] + "\n")
        self.assertEqual(beyin.capture(self.root, self.project, self.payload, "codex"), 1)

    def test_long_message_not_lost(self):
        body = "A" * 55000
        self.write_turns([("user", body)])
        beyin.capture(self.root, self.project, self.payload, "codex")
        records = [beyin.read_json(p) for p in (self.root / "projects/alpha/raw/events").glob("*.json")]
        self.assertEqual(sum(len(m["text"]) for r in records for m in r["messages"]), len(body))
        self.assertTrue(all(sum(len(m["text"]) for m in r["messages"]) <= 24000 for r in records))

    def test_tool_system_reasoning_not_captured(self):
        for kind in ("agent_reasoning", "exec_command_end", "token_count"):
            self.assertIsNone(beyin.message_from({"type": "event_msg", "payload": {"type": kind, "message": "secret"}}, "codex"))
        self.assertIsNone(beyin.message_from({"type": "response_item", "payload": {"role": "user", "content": "duplicate"}}, "codex"))
        self.assertIsNone(beyin.message_from({"role": "system", "content": "instruction"}, "normalized"))

    def test_claude_and_normalized_input(self):
        claude = {"message": {"role": "user", "content": [{"type": "text", "text": "Merhaba"}, {"type": "tool_result", "content": "hidden"}]}}
        self.assertEqual(beyin.message_from(claude, "claude")["text"], "Merhaba")
        self.assertEqual(beyin.message_from({"role": "assistant", "content": "Yanıt"}, "normalized")["role"], "assistant")

    def test_claude_and_cursor_transcript_envelopes(self):
        records = [
            {"type": "user", "message": {"role": "user", "content": "Kullanıcı metni"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Asistan metni"}, {"type": "thinking", "thinking": "gizli"}]}},
        ]
        for adapter in ("claude", "cursor", "normalized"):
            self.assertEqual(beyin.message_from(records[0], adapter)["role"], "user")
            self.assertEqual(beyin.message_from(records[1], adapter)["text"], "Asistan metni")

    def test_prompt_hook_fallback_keeps_user_text_without_transcript(self):
        payload = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s1",
                              "cwd": self.project["paths"][0], "prompt": "Kayıt için kısa soru."})
        with patch("sys.stdin", io.StringIO(payload)):
            beyin.hook(self.root, "claude")
        events = list((self.root / "projects/alpha/raw/events").glob("*.json"))
        self.assertEqual(len(events), 1)
        event = beyin.read_json(events[0])
        self.assertEqual(event["origin"]["type"], "prompt")
        self.assertEqual(event["messages"][0]["text"], "Kayıt için kısa soru.")

    def test_current_codex_item_completed_captures_both_roles(self):
        # Shapes observed in a real Codex 0.154.0 transcript, with fixture text.
        items = [
            {"type": "UserMessage", "content": [{"type": "text", "text": "Kaydı denetle."}]},
            {"type": "Reasoning", "content": [{"type": "Text", "text": "hidden reasoning"}]},
            {"type": "CommandExecution", "content": [{"type": "Text", "text": "hidden tool output"}]},
            {"type": "AgentMessage", "phase": "final_answer", "content": [
                {"type": "Text", "text": "Kaydı denetledim."},
                {"type": "Image", "text": "hidden image payload"}]},
        ]
        with self.transcript.open("w", encoding="utf-8", newline="\n") as stream:
            for i, item in enumerate(items):
                stream.write(json.dumps({"type": "event_msg", "timestamp": str(i),
                    "payload": {"type": "item_completed", "item": item}}) + "\n")
        self.assertEqual(beyin.capture(self.root, self.project, self.payload, "codex"), 1)
        event = beyin.read_json(next((self.root / "projects/alpha/raw/events").glob("*.json")))
        self.assertEqual([(m["role"], m["text"]) for m in event["messages"]],
            [("user", "Kaydı denetle."), ("assistant", "Kaydı denetledim.")])
        self.assertEqual(beyin.capture(self.root, self.project, self.payload, "codex"), 0)

    def test_assistant_proposal_cannot_become_user_decision(self):
        event = self.event()
        result = beyin.validate_summary(self.summary(event, assistant=True), event)
        self.assertEqual(result["items"][0]["kind"], "proposal")
        self.assertTrue(result["items"][0]["uncertain"])

    def test_fabricated_evidence_rejected(self):
        event = self.event()
        result = self.summary(event)
        result["items"][0]["evidence_quote"] = "Kullanıcı bütün dosyaları silmemi istedi."
        with self.assertRaises(ValueError):
            beyin.validate_summary(result, event)
        result = self.summary(event)
        result["items"][0]["evidence_ids"] = ["unknown"]
        with self.assertRaises(ValueError):
            beyin.validate_summary(result, event)

    def test_model_cannot_choose_write_paths(self):
        event = self.event()
        result = self.summary(event)
        result["items"][0]["path"] = "../../AGENTS.md"
        with self.assertRaises(ValueError):
            beyin.validate_summary(result, event)
        self.assertNotIn("/", beyin.topic_id("../../AGENTS.md"))
        with self.assertRaises(ValueError):
            beyin.safe_project(self.root, "../../outside")

    def test_split_models_keep_luna_on_summary_only(self):
        event = self.event()
        calls = []

        def provider(root, settings, prompt, schema, schema_name):
            calls.append((settings["model"], schema_name, prompt))
            if schema_name == "memory_summary":
                return {"summary": "Oturumda özetleyici tercihi konuşuldu."}, {"role": "summary"}
            return {"items": []}, {"role": "extractor"}

        with patch.object(beyin, "run_provider", side_effect=provider):
            result, usage = beyin.run_model(self.root, event, [])
        self.assertEqual([row[:2] for row in calls], [
            ("gpt-5.6-luna", "memory_summary"),
            ("gpt-5.6-sol", "memory_items"),
        ])
        self.assertIn("Karar, tercih, düzeltme veya görev listesi çıkarma", calls[0][2])
        self.assertIn("summary üretme", calls[1][2])
        self.assertEqual(result["items"], [])
        self.assertEqual(usage["summary"]["role"], "summary")
        self.assertEqual(usage["extractor"]["role"], "extractor")

    def test_split_models_record_both_model_roles_and_count_calls(self):
        event = self.event()
        user = event["messages"][0]

        def provider(root, settings, prompt, schema, schema_name):
            if schema_name == "memory_summary":
                return {"summary": "Özetleyici tercihi kaydedildi."}, {}
            return {"items": [{"kind": "decision", "text": user["text"],
                    "topic": "Özetleyici seçimi", "evidence_ids": [user["id"]],
                    "evidence_quote": user["text"], "uncertain": False}]}, {}

        with patch.object(beyin, "run_provider", side_effect=provider):
            result = beyin.process(self.root)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(beyin.read_json(self.root / ".state" / "budget.json")["calls"], 2)
        record = beyin.read_json(next((self.root / "projects/alpha/records").glob("*.json")))
        self.assertEqual(record["summary_model"], "gpt-5.6-luna")
        self.assertEqual(record["extraction_model"], "gpt-5.6-sol")
        self.assertEqual(record["usage"], {"summary": {}, "extractor": {}})

    def test_worker_error_keeps_source_and_queue(self):
        self.event()
        result = beyin.process(self.root, runner=lambda *a: (_ for _ in ()).throw(ValueError("connection unavailable")))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["pending"], 1)
        self.assertEqual(len(list((self.root / "projects/alpha/raw/events").glob("*.json"))), 1)
        self.assertFalse((self.root / "projects/alpha/records").exists())

    def test_success_idempotent_rebuild_and_links(self):
        self.event()
        calls = []
        def runner(root, event, topics):
            calls.append(event["id"])
            return self.summary(event), {}
        self.assertEqual(beyin.process(self.root, runner=runner)["processed"], 1)
        self.assertEqual(beyin.process(self.root, runner=runner)["processed"], 0)
        base = self.root / "projects/alpha"
        before = {p.relative_to(base): p.read_bytes() for p in base.rglob("*.md")}
        beyin.rebuild(self.root, "alpha")
        self.assertEqual(before, {p.relative_to(base): p.read_bytes() for p in base.rglob("*.md")})
        self.assertEqual(len(calls), 1)
        self.assertIn("Özetleyici Luna olsun", (base / "DECISIONS.md").read_text(encoding="utf-8"))
        self.assertFalse((self.root / "projects/beta/records").exists())
        import re
        for p in base.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
                self.assertTrue((p.parent / target).exists(), (p, target))

    def test_local_search_supports_topic_aliases_and_context_query(self):
        event = self.event()
        with patch.object(beyin, "run_model", return_value=(self.summary(event), {})):
            self.assertEqual(beyin.process(self.root)["processed"], 1)
        beyin.add_aliases(self.root, "alpha", "Özetleyici seçimi", ["model tercihi", "özet modeli"])
        result = beyin.search(self.root, "alpha", "model tercihi")
        self.assertEqual(result["results"][0]["topic"], "Özetleyici seçimi")
        self.assertIn("model tercihi", result["results"][0]["aliases"])
        context = beyin.context_for(self.root, self.project, "model tercihi", 3)
        self.assertIn("Yerel hafıza araması: model tercihi", context)
        self.assertIn("Özetleyici seçimi", context)

    def test_preferences_profiles_change_only_processing_controls(self):
        original_summary = beyin.config(self.root)["summarizer"]
        result = beyin.preferences(self.root, "economical")
        self.assertEqual(result["profile"], "economical")
        self.assertTrue(result["auto_process"])
        self.assertEqual(result["max_calls_per_run"], 2)
        self.assertEqual(result["max_calls_per_day"], 8)
        self.assertEqual(beyin.config(self.root)["summarizer"], original_summary)
        result = beyin.preferences(self.root, "manual")
        self.assertEqual(result["profile"], "manual")
        self.assertFalse(result["auto_process"])

    def test_source_mutation_rejected(self):
        self.event()
        source = next((self.root / "projects/alpha/raw/events").glob("*.json"))
        source.write_text("{}")
        called = []
        result = beyin.process(self.root, runner=lambda *args: called.append(True))
        self.assertEqual(result["status"], "error")
        self.assertFalse(called)

    def test_worker_lock_prevents_parallel_calls(self):
        self.event()
        with beyin.lock(self.root / ".state/worker.lock") as held:
            self.assertTrue(held)
            self.assertEqual(beyin.process(self.root)["status"], "busy")

    def test_temporary_budget_expires_without_changing_normal_limits(self):
        cfg = beyin.config(self.root)
        cfg.update(max_calls_per_day=60, max_calls_per_run=8,
                   temporary_budget={"until":"2026-09-25T14:00:00+00:00", "max_calls_per_day":200})
        before = beyin.dt.datetime.fromisoformat("2026-09-25T13:59:59+00:00")
        expiry = beyin.dt.datetime.fromisoformat("2026-09-25T14:00:00+00:00")
        self.assertEqual(beyin.processing_limits(cfg, before)["max_calls_per_day"], 200)
        self.assertEqual(beyin.processing_limits(cfg, expiry)["max_calls_per_day"], 60)
        self.assertEqual(cfg["max_calls_per_day"], 60)
        self.assertEqual(beyin.processing_limits(cfg, before)["max_calls_per_run"], 8)

    def test_worker_uses_temporary_budget_but_preserves_spent_calls(self):
        self.event()
        cfg = beyin.config(self.root)
        cfg.update(max_calls_per_day=1, temporary_budget={
            "until":(beyin.dt.datetime.now(beyin.dt.timezone.utc)+beyin.dt.timedelta(days=1)).isoformat(),
            "max_calls_per_day":2})
        beyin.atomic(self.root / "config.json", cfg)
        beyin.atomic(self.root / ".state/budget.json", {
            "date":beyin.dt.datetime.now(beyin.dt.timezone.utc).date().isoformat(), "calls":1})
        result = beyin.process(self.root, runner=lambda root,event,topics:(self.summary(event),{}))
        self.assertEqual(result["processed"], 1)
        self.assertEqual(beyin.read_json(self.root / ".state/budget.json")["calls"], 2)

    def test_invalid_evidence_does_not_block_other_jobs(self):
        first = self.event()
        self.write_turns([("user", "Yeni karar: belgeler Türkçe olsun.")], append=True)
        beyin.capture(self.root, self.project, self.payload, "codex")
        def runner(root, event, topics):
            result = self.summary(event)
            if event["id"] == first["id"]:
                result["items"][0]["evidence_quote"] = "fabricated evidence"
            return result, {}
        result = beyin.process(self.root, runner=runner)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertFalse((self.root / ".state/PAUSED").exists())
        self.assertFalse((self.root / "projects/alpha/records" / (first["id"] + ".json")).exists())
        for _ in range(2):
            beyin.process(self.root, force=True, runner=runner)
        job = beyin.read_json(next((self.root / ".queue").glob("*.json")))
        self.assertTrue(job["needs_review"])
        with patch.object(beyin, "run_model") as model:
            beyin.process(self.root)
            model.assert_not_called()
        recovered = beyin.process(self.root, force=True,
                                  runner=lambda root, event, topics: (self.summary(event), {}))
        self.assertEqual(recovered["processed"], 1)

    def test_budget_and_auth_pause(self):
        self.event()
        runner = lambda *a: (_ for _ in ()).throw(ValueError("Codex CLI oturum açılması gerekiyor (codex login)"))
        beyin.process(self.root, runner=runner)
        self.assertTrue((self.root / ".state/PAUSED").exists())
        self.assertEqual(beyin.process(self.root, runner=runner)["status"], "paused_after_error")
        event = beyin.read_json(next((self.root / "projects/alpha/raw/events").glob("*.json")))
        self.assertEqual(beyin.process(self.root, force=True, runner=lambda *a: (self.summary(event), {}))["processed"], 1)

    def test_project_isolation_and_git_worktree(self):
        self.assertEqual(beyin.project_for(self.root, self.project["paths"][0] + "/src")["id"], "alpha")
        self.assertIsNone(beyin.project_for(self.root, self.project["paths"][0] + "-different"))
        with patch.object(beyin, "git_identity", return_value="common-git"):
            registry = beyin.read_json(self.root / "projects.json")
            registry["projects"][0]["git_common_dir"] = "common-git"
            beyin.atomic(self.root / "projects.json", registry)
            self.assertEqual(beyin.project_for(self.root, str(Path(self.temp.name) / "new-worktree"))["id"], "alpha")

    def test_ingest_original_preserved_and_deduplicated(self):
        document = Path(self.temp.name) / "note.md"
        document.write_text("# Kaynak\nYeni sürüm henüz öneri aşamasında.", encoding="utf-8")
        first = beyin.ingest(self.root, "alpha", document, "Not")
        second = beyin.ingest(self.root, "alpha", document, "Not")
        self.assertEqual(first, second)
        sources = list((self.root / "projects/alpha/raw/sources").iterdir())
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].read_bytes(), document.read_bytes())
        self.assertEqual(len(list((self.root / ".queue").glob("*.json"))), 1)

    def test_integration_merge_preserves_other_hooks_and_instructions(self):
        home = Path(self.temp.name) / "codex-home"
        home.mkdir()
        (home / "AGENTS.md").write_text("Existing rule: do not publish.\n")
        original_hook = {"type": "command", "command": "existing-check", "timeout": 2}
        beyin.atomic(home / "hooks.json", {"hooks": {"Stop": [{"hooks": [original_hook]}]}})
        first = install.integrations(self.root, home)
        for path, content in first.items():
            beyin.atomic(path, content)
        second = install.integrations(self.root, home)
        self.assertEqual(first, second)
        hooks = json.loads(second[home / "hooks.json"])
        self.assertEqual(hooks["hooks"]["Stop"][0]["hooks"][0], original_hook)
        self.assertIn("Existing rule: do not publish.", second[home / "AGENTS.md"])

    def test_claude_integration_merges_settings_and_user_memory(self):
        home = Path(self.temp.name) / "claude-home"
        home.mkdir()
        (home / "CLAUDE.md").write_text("Existing Claude rule.\n")
        beyin.atomic(home / "settings.json", {"permissions": {"deny": ["rm -rf"]},
                                               "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "existing-check"}]}]}})
        first = install.integrations(self.root, claude_home=home)
        for path, content in first.items():
            beyin.atomic(path, content)
        second = install.integrations(self.root, claude_home=home)
        self.assertEqual(first, second)
        settings = json.loads(second[home / "settings.json"])
        self.assertEqual(settings["permissions"]["deny"], ["rm -rf"])
        self.assertEqual(set(settings["hooks"]), set(install.CLAUDE_EVENTS))
        commands = [h["command"] for groups in settings["hooks"].values() for group in groups for h in group["hooks"]]
        self.assertTrue(any("--adapter claude" in command for command in commands))
        self.assertIn("Existing Claude rule.", second[home / "CLAUDE.md"])

    def test_redaction(self):
        text = "api_key=sk-abcdefghijklmnopqrstuvwxyz password=hunter2 Bearer abc123"
        clean = beyin.redact(text)
        self.assertNotIn("hunter2", clean)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", clean)
        self.assertNotIn("abc123", clean)


if __name__ == "__main__":
    unittest.main(verbosity=2)
