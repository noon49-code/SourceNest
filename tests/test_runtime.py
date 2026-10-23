"""Synthetic offline coverage: no private vaults, real keys or provider calls."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "engine"))
sys.path.insert(0, str(PACKAGE))
import beyin
import install
import portable
import maintenance
import knowledge
import advisor
import clients
import build_release


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "vault"
        with patch("install.shutil.which", return_value=None):
            install.install(self.root, None, {"schema_version": 1, "projects": []})
        self.project = self.base / "project"
        self.project.mkdir()
        with patch("beyin.git_identity", return_value=None):
            beyin.register(self.root, "demo", self.project, "Demo")
        cfg = beyin.config(self.root)
        cfg.update(auto_process=False, git_checkpoints=False)
        beyin.atomic(self.root / "config.json", cfg)

    def tearDown(self):
        self.temp.cleanup()

    def note(self, **extra):
        data = dict(project="demo", title="Database choice", body="Use SQLite for the local prototype.", slug="database")
        data.update(extra)
        knowledge.create(self.root, data)
        return knowledge.sources(self.root, "demo")[0]

    def package(self, extras=None, version="2.1.0"):
        files = {"engine/beyin.py": ('VERSION = "' + version + '"\n').encode(), "beyin.py": b"# new launcher\n", ".sourcenest-version": version.encode()}
        files.update(extras or {})
        path = self.base / "release.zip"
        manifest = {"schema_version": 1, "product": "SourceNest", "version": version, "files": {n: portable.sha(d) for n, d in files.items()}}
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest))
        Path(str(path) + ".sha256").write_text(portable.sha(path.read_bytes()))
        return path

    def test_package_update_rollback_preserve_private_data_and_counter(self):
        note = self.note()
        budget = {"date": "2026-10-23", "calls": 182}
        beyin.atomic(self.root / ".state/budget.json", budget)
        before = (self.root / "engine/beyin.py").read_bytes()
        package = self.package()
        self.assertEqual(maintenance.update(self.root, package, check=True)["status"], "available")
        self.assertFalse((self.root / "beyin.py").exists())
        self.assertEqual(maintenance.update(self.root, package)["status"], "updated")
        self.assertEqual(maintenance.update(self.root, package)["status"], "noop")
        self.assertEqual(maintenance.restore(self.root)["status"], "rolled_back")
        self.assertEqual((self.root / "engine/beyin.py").read_bytes(), before)
        self.assertFalse((self.root / "beyin.py").exists())
        self.assertEqual(portable.read(self.root / ".state/budget.json"), budget)
        self.assertEqual(knowledge.sources(self.root, "demo")[0]["source_sha256"], note["source_sha256"])

    def test_recover_interrupted_update_before_next_upgrade(self):
        package = self.package()
        before = (self.root / "engine/beyin.py").read_bytes()
        real_write = maintenance.write
        def crash(path, data):
            if Path(path).name == ".sourcenest-version":
                raise OSError("synthetic power loss")
            return real_write(path, data)
        with patch("maintenance.write", side_effect=crash):
            with self.assertRaises(OSError):
                maintenance.update(self.root, package)
        with self.assertRaisesRegex(ValueError, "recover first"):
            maintenance.update(self.root, package)
        self.assertEqual(maintenance.restore(self.root, recover=True)["status"], "recovered")
        self.assertEqual((self.root / "engine/beyin.py").read_bytes(), before)

    def test_update_and_restore_refuse_user_edits(self):
        package = self.package()
        path = self.root / "engine/beyin.py"
        path.write_bytes(path.read_bytes() + b"# customization\n")
        self.assertEqual(maintenance.update(self.root, package, check=True)["status"], "conflicts")
        with self.assertRaisesRegex(ValueError, "conflict"):
            maintenance.update(self.root, package)
        # A conflict did not create a transaction or overwrite the source.
        self.assertFalse((self.root / ".state/maintenance.json").exists())

    def test_rollback_refuses_later_edits(self):
        maintenance.update(self.root, self.package())
        path = self.root / "beyin.py"
        path.write_text("# later user edit")
        with self.assertRaisesRegex(ValueError, "later user edit"):
            maintenance.restore(self.root)
        self.assertEqual(path.read_text(), "# later user edit")

    def test_archive_rejects_user_data_path_and_checksum_mismatch(self):
        package = self.package({"PROFILE.md": b"overwrite identity"})
        with self.assertRaisesRegex(ValueError, "user data"):
            maintenance.package_files(package)
        Path(str(package) + ".sha256").write_text("0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            maintenance.package_files(package)

    def test_archive_rejects_traversal_symlinks_and_duplicates(self):
        for name, symlink in (("../escape", False), ("C:/escape", False), ("engine/link.py", True)):
            package = self.package()
            with zipfile.ZipFile(package, "a") as archive:
                item = zipfile.ZipInfo(name)
                if symlink:
                    item.create_system = 3
                    item.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(item, "target")
            Path(str(package) + ".sha256").write_text(portable.sha(package.read_bytes()))
            with self.assertRaises(ValueError):
                maintenance.package_files(package)

    def test_official_release_names_stable_tag_and_host_validation(self):
        release = {"tag_name": "v2.1.0", "draft": False, "prerelease": False,
                   "assets": [{"name": n, "browser_download_url": "https://github.com/noon49-code/SourceNest/releases/download/v2.1.0/" + n} for n in ("SourceNest-2.1.0.zip", "SourceNest-2.1.0.zip.sha256")]}
        self.assertEqual(maintenance.latest_release(lambda url: json.dumps(release).encode())["version"], "2.1.0")
        release["prerelease"] = True
        with self.assertRaises(ValueError):
            maintenance.latest_release(lambda url: json.dumps(release).encode())

    def test_external_state_migration_preserves_counter_and_cursor(self):
        old = self.root / ".state"
        portable.write(old / "budget.json", {"date": "2026-10-23", "calls": 182})
        portable.write(old / "cursors/demo.json", {"offset": 100})
        destination = self.base / "runtime"
        portable.migrate_state(self.root, destination)
        self.assertEqual(portable.state_dir(self.root), destination)
        self.assertEqual(portable.read(destination / "budget.json")["calls"], 182)
        self.assertEqual(portable.read(destination / "cursors/demo.json")["offset"], 100)
        self.assertTrue((old / "budget.json").exists())
        self.assertFalse((destination / "installation.json").exists())

    def test_state_paths_reject_sync_folders_and_in_vault(self):
        for path in (self.root / "state", self.base / "OneDrive/state", Path("relative")):
            with self.assertRaises(ValueError):
                portable.validate_state(self.root, path)
        with patch.dict(os.environ, {"SOURCENEST_STATE_HOME": str(self.base / "state-home")}):
            for platform in ("win32", "darwin", "linux"):
                self.assertTrue(portable.default_state(self.root, platform).is_relative_to(self.base / "state-home"))

    def test_notes_are_safe_idempotent_and_locally_retrievable(self):
        note = self.note(aliases=["storage"])
        self.note(aliases=["storage"])
        self.assertEqual(knowledge.lookup(self.root, "demo", "storage")[0]["id"], note["id"])
        with self.assertRaises(ValueError):
            self.note(body="replace human source")
        with self.assertRaises(ValueError):
            self.note(folder="../escape")
        with self.assertRaises(ValueError):
            self.note(remote_allowed="true")
        self.assertFalse(advisor.eligible(note))
        self.assertEqual(knowledge.sync(self.root)["model_calls"], 0)

    def test_companion_never_fabricates_identity_or_overwrites_sources(self):
        self.assertEqual(knowledge.companion(self.root)["status"], "not_configured")
        self.assertFalse((self.root / "companion").exists())
        knowledge.companion(self.root, {"name": "Synthetic Example", "preferences": "Use short notes."})
        with self.assertRaises(ValueError):
            knowledge.companion(self.root, {"name": "Different"})
        (self.root / "Soul.md").write_text("Existing user identity")
        self.assertEqual(knowledge.companion(self.root)["status"], "needs_attention")

    def test_cross_session_verification_needs_two_deliveries_and_current_hash(self):
        note = self.note()
        knowledge.record_delivery(self.root, "demo", "session-one", [note])
        self.assertFalse(knowledge.verify_session(self.root, "demo", note["id"])["verified"])
        knowledge.record_delivery(self.root, "demo", "session-two", [note])
        self.assertTrue(knowledge.verify_session(self.root, "demo", note["id"])["verified"])
        path = self.root / note["source"]
        path.write_bytes(path.read_bytes() + b"\nchanged")
        self.assertFalse(knowledge.verify_session(self.root, "demo", note["id"])["verified"])

    def test_advisor_off_makes_no_key_or_transport_calls(self):
        note = self.note()
        with patch("advisor.key_for", side_effect=AssertionError("No key access")):
            result = advisor.evaluate(self.root, "demo", "Database?", [note], send=lambda *args: self.fail("No network"))
        self.assertEqual(result["mode"], "off")

    def test_advisor_filters_private_sensitive_remote_disabled_before_send(self):
        note = self.note()
        advisor.configure(self.root, "shadow")
        for changes in ({}, {"visibility": "internal", "remote_allowed": False}, {"visibility": "internal", "remote_allowed": True, "sensitivity": "sensitive"}):
            source = dict(note, **changes)
            result = advisor.evaluate(self.root, "demo", "query", [source], send=lambda *args: self.fail("Privacy leak"))
            self.assertEqual(result["http_requests"], 0)

    def test_shadow_scores_never_change_order_and_cache_has_no_text(self):
        note = self.note(visibility="internal", remote_allowed=True)
        advisor.configure(self.root, "shadow")
        calls = []
        def send(*args):
            calls.append(args)
            return {"answers": {"support": {"type": "noul", "noul": 0.9}}}
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic-key"}):
            result = advisor.context(self.root, "demo", "storage", [note], send=send)
            advisor.context(self.root, "demo", "storage", [note], send=send)
        self.assertEqual(result["records"], [note])
        self.assertEqual(len(calls), 1)
        cache = next((self.root / ".state/advisor-cache").glob("*.json")).read_text()
        self.assertNotIn("SQLite", cache)
        self.assertNotIn("synthetic-key", (self.root / ".state/advisor-calls.json").read_text())

    def test_provider_failure_invalid_score_and_source_change_fall_back(self):
        note = self.note(visibility="public", remote_allowed=True)
        advisor.configure(self.root, "on")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic-key"}):
            bad = advisor.context(self.root, "demo", "query", [note], send=lambda *args: {"answers": {"support": {"type": "noul", "noul": float("nan")}}})
            self.assertTrue(bad["advisor"]["degraded"])
            def mutate(*args):
                path = self.root / note["source"]
                path.write_bytes(path.read_bytes() + b"changed")
                return {"answers": {"support": {"type": "noul", "noul": 0.9}}}
            result = advisor.evaluate(self.root, "demo", "different query", [note], send=mutate)
        self.assertEqual(result["reason"], "source_changed")
        self.assertEqual(result["scores"], {})

    def test_laya_loopback_shadow_only_no_typesafe_key(self):
        with self.assertRaises(ValueError):
            advisor.configure(self.root, "on", provider="laya")
        with self.assertRaises(ValueError):
            advisor.configure(self.root, "shadow", provider="laya", base_url="http://localhost:8765")
        advisor.configure(self.root, "shadow", provider="laya")
        note = self.note(visibility="internal", remote_allowed=True)
        def send(url, payload, key, timeout, local):
            self.assertEqual(key, "")
            self.assertTrue(local)
            self.assertTrue(url.startswith("http://127.0.0.1:8765"))
            return {"routing": {"model": "multilingual"}, "usage": {"input_tokens": 100}, "answers": {"support": {"type": "noul", "noul": 0.2}}}
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "must-not-leak", "LAYA_API_KEY": ""}):
            self.assertFalse(advisor.evaluate(self.root, "demo", "query", [note], send=send)["degraded"])

    def test_advisor_counter_respects_main_daily_budget_and_kill_switch(self):
        note = self.note(visibility="public", remote_allowed=True)
        advisor.configure(self.root, "on", enable=["auto_context"])
        cap = beyin.processing_limits(beyin.config(self.root))["max_calls_per_day"]
        portable.write(self.root / ".state/budget.json", {"date": dt.datetime.now(dt.timezone.utc).date().isoformat(), "calls": cap})
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic"}):
            result = advisor.evaluate(self.root, "demo", "query", [note], send=lambda *args: self.fail("over budget"))
            self.assertEqual(result["reason"], "daily_budget")
        with patch.dict(os.environ, {"SOURCENEST_ADVISOR_DISABLE": "1"}):
            self.assertEqual(advisor.status(self.root)["mode"], "off")

    def test_review_never_writes_and_rejects_fabricated_quote(self):
        note = self.note(visibility="internal", remote_allowed=True)
        evidence = [{"record_id": note["id"], "source_sha256": note["source_sha256"], "quote": "fabricated quote"}]
        result = advisor.review(self.root, "demo", "claim", evidence)
        self.assertFalse(result["approved"])
        self.assertFalse(result["memory_written"])
        self.assertEqual(result["reason"], "invalid_evidence")

    def test_clients_preserve_unrelated_hooks_and_are_idempotent(self):
        target = self.project / ".codex/hooks.json"
        portable.write(target, {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "unrelated-hook"}]}]}})
        selected = list(clients.SUPPORTED)
        clients.install(self.root, selected, workspace=self.project)
        clients.install(self.root, selected, workspace=self.project)
        groups = portable.read(target)["hooks"]["SessionStart"]
        commands = [h["command"] for g in groups for h in g["hooks"]]
        self.assertEqual(len(commands), 2)
        self.assertIn("unrelated-hook", commands)
        self.assertTrue((self.project / ".opencode/plugins/sourcenest.js").exists())
        self.assertTrue((self.project / ".kiro/skills/sourcenest/SKILL.md").exists())
        self.assertEqual((self.project / "CLAUDE.md").read_text().strip(), "@AGENTS.md")

    def test_client_rollback_and_modified_skill_conflict(self):
        clients.install(self.root, ["kiro"], workspace=self.project)
        self.assertEqual(clients.restore(self.root, workspace=self.project)["status"], "rolled_back")
        self.assertFalse((self.project / ".kiro/hooks/sourcenest.json").exists())
        clients.install(self.root, ["kiro"], workspace=self.project)
        skill = self.project / ".agents/skills/sourcenest/SKILL.md"
        skill.write_text("User custom skill")
        with self.assertRaisesRegex(ValueError, "skill conflict"):
            clients.install(self.root, ["kiro"], workspace=self.project)

    def test_package_builder_excludes_private_runtime_and_produces_valid_archive(self):
        result = build_release.build(self.base / "distribution")
        manifest, files = maintenance.package_files(result["package"])
        self.assertEqual(manifest["version"], "2.0.0")
        self.assertNotIn("config.json", files)
        with zipfile.ZipFile(result["source"]) as archive:
            self.assertIn("setup.py", archive.namelist())
            self.assertFalse(any(n.startswith((".git/", "projects/", ".state/")) for n in archive.namelist()))

    def test_real_separate_process_note_readback(self):
        self.note()
        result = subprocess.run([sys.executable, str(PACKAGE / "engine/beyin.py"), "--root", str(self.root), "context", "--project", "demo", "--query", "SQLite", "--json"], capture_output=True, text=True, check=True)
        response = json.loads(result.stdout)
        self.assertEqual(response["records"][0]["source"], "projects/demo/notes/database.md")
        self.assertEqual(response["model_calls"], 0)


    def test_generated_javascript_is_valid_and_opencode_context_is_delivered(self):
        if not shutil.which('node'):
            self.skipTest('Node unavailable; Python runtime does not require Node')
        self.note()
        changes, _ = clients.plan(self.root, ['opencode', 'omp'], self.project)
        for name in ('.opencode/plugins/sourcenest.js', '.omp/hooks/pre/sourcenest.ts'):
            script = self.base / (name.split('/')[-1] + '.mjs')
            script.write_bytes(changes[name])
            subprocess.run(['node', '--check', str(script)], check=True, capture_output=True)
        module = self.base / 'sourcenest.js.mjs'
        code = "import {SourceNest} from " + json.dumps(module.as_uri()) + ";\n"
        code += "const hooks=await SourceNest({directory:" + json.dumps(str(self.project)) + ",client:{session:{get:async()=>({data:{}})}}});\n"
        code += "await hooks['chat.message']({sessionID:'synthetic-session'},{parts:[{type:'text',text:'SQLite'}]});const out={system:[]};await hooks['experimental.chat.system.transform']({sessionID:'synthetic-session'},out);if(!out.system.join().includes('SQLite'))throw Error('missing delivered context');"
        check = self.base / 'test-client.mjs'
        check.write_text(code, encoding='utf-8')
        subprocess.run(['node', str(check)], check=True, capture_output=True, timeout=30)

    def test_hermes_callbacks_deliver_registered_project_context(self):
        import hermes_bridge
        self.note()
        registered = {}
        class Context:
            def register_hook(self, name, callback):
                registered[name] = callback
        hermes_bridge.register(Context(), self.root)
        result = registered['pre_llm_call'](session_id='hermes-example', cwd=str(self.project), prompt='database')
        self.assertIn('SQLite', result['context'])
        registered['on_session_finalize'](session_id='hermes-example', cwd=str(self.project))

    def test_plain_text_bridge_and_two_separate_hook_sessions(self):
        self.note()
        for session in ('first-actual-process', 'second-actual-process'):
            payload = dict(cwd=str(self.project), session_id=session, hook_event_name='SessionStart')
            result = subprocess.run([sys.executable, str(PACKAGE / 'engine/beyin.py'), '--root', str(self.root), 'hook', '--adapter', 'normalized'], input=json.dumps(payload), capture_output=True, text=True, check=True)
            self.assertIn('SQLite', json.loads(result.stdout)['hookSpecificOutput']['additionalContext'])
        record = knowledge.sources(self.root, 'demo')[0]
        self.assertTrue(knowledge.verify_session(self.root, 'demo', record['id'])['verified'])
        import client_bridge
        self.assertIn('SQLite', client_bridge.run(self.root, 'kiro', 'SessionStart', {'cwd':str(self.project), 'session_id':'kiro-example'}))

    def test_fresh_cross_platform_setup_with_explicit_external_state(self):
        vault = self.base / 'new-vault'
        state = self.base / 'new-state'
        result = subprocess.run([sys.executable, str(PACKAGE / 'setup.py'), '--vault', str(vault), '--state', str(state), '--workspace', str(self.project), '--project', 'demo', '--client', 'kiro', '--apply'], capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(json.loads(result.stdout)['status'], 'installed')
        self.assertEqual(portable.state_dir(vault), state)
        self.assertEqual((vault / '.sourcenest-version').read_text().strip(), '2.0.0')
        self.assertTrue((vault / 'beyin.py').exists())
        commands = subprocess.run([sys.executable, str(vault / 'beyin.py'), 'preferences', '--human'], capture_output=True, text=True, check=True)
        self.assertIn('Profile:', commands.stdout)
        self.assertFalse((vault / 'companion/Core.md').exists())

    def test_package_rollback_detects_corrupted_backup(self):
        maintenance.update(self.root, self.package())
        journal = self.root / '.state/maintenance.json'
        data = portable.read(journal)
        data['entries'][0]['before'] = maintenance._encoded(b'corrupted backup')
        portable.write(journal, data)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            maintenance.restore(self.root)

    def test_api_rate_limit_uses_official_latest_redirect(self):
        import urllib.error
        def limited(url):
            raise urllib.error.HTTPError(url, 429, 'limited', {}, None)
        result = maintenance.latest_release(limited, lambda: 'https://github.com/noon49-code/SourceNest/releases/tag/v2.1.0')
        self.assertIn('/v2.1.0/SourceNest-2.1.0.zip', result['package_url'])
        with self.assertRaises(ValueError):
            maintenance.latest_release(limited, lambda: 'https://evil.example/releases/tag/v2.1.0')

    def test_legacy_engine_rollback_removes_only_new_modules(self):
        original = {'engine/beyin.py', 'engine/Beyin.ps1', 'engine/Beyin.cmd'}
        for name in install.MANAGED_ENGINE:
            if name not in original:
                (self.root / name).unlink()
        meta = portable.read(self.root / '.state/installation.json')
        meta['managed_engine_sha256'] = install.managed_hashes(self.root)
        portable.write(self.root / '.state/installation.json', meta)
        install.upgrade(self.root)
        self.assertTrue((self.root / 'engine/portable.py').exists())
        install.rollback_engine(self.root)
        self.assertFalse((self.root / 'engine/portable.py').exists())
        self.assertTrue((self.root / 'engine/beyin.py').exists())


    def test_reserved_archive_paths_and_desktop_argument_escaping(self):
        for name in ('engine/CON.py', 'engine/name.py.', 'engine/name.py ', 'engine/../escape.py'):
            with self.assertRaises(ValueError):
                portable.child(self.root, name)
        result = portable.desktop_file(Path('/tmp/project $value percent% space'), '/usr/bin/python3').decode()
        self.assertIn('Exec="/usr/bin/python3" "', result)
        self.assertIn('percent%%', result)
        self.assertNotIn("Exec='", result)

    def test_desktop_cli_selection_prefers_installed_host_before_old_path(self):
        appdata = self.base / 'appdata'
        host = appdata / 'OpenAI/Codex/bin/current/codex.exe'
        host.parent.mkdir(parents=True)
        host.write_bytes(b'synthetic placeholder')
        with patch.dict(os.environ, {'LOCALAPPDATA': str(appdata), 'CODEX_CLI_PATH': ''}), patch('beyin.sys.platform', 'win32'), patch('beyin.shutil.which', return_value='old-codex.cmd'):
            self.assertEqual(beyin.codex_binary({}), str(host))

    def test_interrupted_client_install_recovers_shared_user_instructions(self):
        agents = self.project / 'AGENTS.md'
        agents.write_text('Keep my original rules.', encoding='utf-8')
        real_write = clients.write
        def crash(path, data):
            if Path(path).name == 'AGENTS.md':
                raise OSError('synthetic interruption')
            return real_write(path, data)
        with patch('clients.write', side_effect=crash):
            with self.assertRaises(OSError):
                clients.install(self.root, ['codex'], workspace=self.project)
        self.assertEqual(clients.restore(self.root, recover=True, workspace=self.project)['status'], 'recovered')
        self.assertEqual(agents.read_text(encoding='utf-8'), 'Keep my original rules.')
        self.assertFalse((self.project / '.codex/hooks.json').exists())

    def test_laya_rejects_truncated_input_and_imports_no_model_runtime(self):
        note = self.note(visibility='internal', remote_allowed=True)
        advisor.configure(self.root, 'shadow', provider='laya')
        response = {'routing':{'model':'multilingual'},'usage':{'input_tokens':1024},'answers':{'support':{'type':'noul','noul':0.8}}}
        result = advisor.evaluate(self.root, 'demo', 'database', [note], send=lambda *args:response)
        self.assertEqual(result['reason'], 'laya_state_truncated')
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('laya', sys.modules)
