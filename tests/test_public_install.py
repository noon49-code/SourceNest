import json
from pathlib import Path
import tempfile
import unittest
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import install

class PublicInstallTests(unittest.TestCase):
    def test_clean_install_and_registration_preserve_existing_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / 'fake-codex'
            home.mkdir()
            (home / 'AGENTS.md').write_text('Keep existing rules.\n')
            vault = base / 'vault'
            registry = json.loads((PACKAGE / 'projects.example.json').read_text())
            install.install(vault, home, registry)
            self.assertIn('Keep existing rules.', (home / 'AGENTS.md').read_text())
            hooks = json.loads((home / 'hooks.json').read_text())['hooks']
            self.assertEqual(set(hooks), set(install.EVENTS))
            self.assertEqual(sum(len(g['hooks']) for groups in hooks.values() for g in groups), 5)
            self.assertEqual((vault / '.gitignore').read_bytes(), (PACKAGE / 'vault.gitignore').read_bytes())
            project = base / 'project'
            project.mkdir()
            install.beyin.register(vault, 'example', project, 'Example')
            self.assertEqual(install.beyin.project_for(vault, project)['id'], 'example')
            self.assertTrue((vault / 'projects/example/wiki/index.md').exists())
            with self.assertRaises(ValueError):
                install.install(vault, home, registry)

    def test_clean_install_can_connect_codex_and_claude_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / 'fake-codex'
            claude_home = base / 'fake-claude'
            codex_home.mkdir()
            claude_home.mkdir()
            vault = base / 'vault'
            registry = json.loads((PACKAGE / 'projects.example.json').read_text())
            install.install(vault, codex_home, registry, claude_home)
            self.assertTrue((codex_home / 'hooks.json').exists())
            self.assertTrue((claude_home / 'settings.json').exists())
            self.assertTrue((claude_home / 'CLAUDE.md').exists())
            settings = json.loads((claude_home / 'settings.json').read_text())
            self.assertEqual(set(settings['hooks']), set(install.CLAUDE_EVENTS))
            self.assertTrue(any('--adapter claude' in hook['command']
                                for groups in settings['hooks'].values()
                                for group in groups for hook in group['hooks']))

    def test_existing_vault_can_add_claude_without_replacing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / 'fake-codex'
            claude_home = base / 'fake-claude'
            codex_home.mkdir()
            claude_home.mkdir()
            vault = base / 'vault'
            registry = json.loads((PACKAGE / 'projects.example.json').read_text())
            install.install(vault, codex_home, registry)
            marker = vault / 'notes-marker.txt'
            marker.write_text('keep this vault data', encoding='utf-8')
            result = install.integrate(vault, claude_home=claude_home)
            self.assertTrue(Path(result['backup']).is_dir())
            self.assertEqual(marker.read_text(encoding='utf-8'), 'keep this vault data')
            self.assertTrue((claude_home / 'settings.json').exists())
            state = json.loads((vault / '.state' / 'installation.json').read_text())
            self.assertEqual(state['integrations'], ['claude', 'codex'])

    def test_existing_vault_upgrade_replaces_only_managed_engine_and_adds_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / 'fake-codex'
            claude_home = base / 'fake-claude'
            codex_home.mkdir()
            claude_home.mkdir()
            vault = base / 'vault'
            registry = json.loads((PACKAGE / 'projects.example.json').read_text())
            install.install(vault, codex_home, registry)
            profile = vault / 'PROFILE.md'
            profile.write_text(profile.read_text(encoding='utf-8') + '\nUser preference.\n', encoding='utf-8')
            result = install.upgrade(vault, claude_home=claude_home)
            self.assertEqual(result['engine_version'], install.beyin.VERSION)
            self.assertIn('User preference.', profile.read_text(encoding='utf-8'))
            self.assertIn(f'VERSION = "{install.beyin.VERSION}"', (vault / 'engine' / 'beyin.py').read_text(encoding='utf-8'))
            self.assertTrue((claude_home / 'settings.json').exists())

    def test_verify_reports_selected_integrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / 'fake-codex'
            claude_home = base / 'fake-claude'
            codex_home.mkdir()
            claude_home.mkdir()
            vault = base / 'vault'
            registry = json.loads((PACKAGE / 'projects.example.json').read_text())
            install.install(vault, codex_home, registry, claude_home)
            report = install.verify(vault, codex_home, claude_home)
            self.assertTrue(report['ok'])
            self.assertEqual(report['engine']['version'], install.beyin.VERSION)
            self.assertTrue(report['engine']['current'])
            self.assertFalse(report['engine']['upgrade_needed'])
            self.assertEqual(report['clients']['codex']['managed_hooks'], len(install.CODEX_EVENTS))
            self.assertEqual(report['clients']['claude']['managed_hooks'], len(install.CLAUDE_EVENTS))


class UpgradeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.vault = base / 'vault'
        self.home = base / 'client'
        self.home.mkdir()
        install.install(self.vault, self.home, {'schema_version': 1, 'projects': []})

    def tearDown(self):
        self.tmp.cleanup()

    def test_upgrade_plan_is_read_only_and_rejects_modified_engine(self):
        engine = self.vault / 'engine/beyin.py'
        engine.write_text(engine.read_text(encoding='utf-8') + '\n# user customization\n', encoding='utf-8')
        state = (self.vault / '.state/installation.json').read_bytes()
        self.assertEqual(install.upgrade_plan(self.vault)['conflicts'], ['engine/beyin.py'])
        with self.assertRaisesRegex(ValueError, 'Upgrade conflict'):
            install.upgrade(self.vault)
        self.assertEqual((self.vault / '.state/installation.json').read_bytes(), state)
        self.assertIn('user customization', engine.read_text(encoding='utf-8'))

    def test_explicit_file_acceptance_and_engine_rollback_preserve_notes(self):
        engine = self.vault / 'engine/beyin.py'
        original = engine.read_text(encoding='utf-8') + '\n# reviewed legacy customization\n'
        engine.write_text(original, encoding='utf-8')
        note = self.vault / 'user-note.md'
        note.write_text('keep this source', encoding='utf-8')
        install.upgrade(self.vault, accepted=['engine/beyin.py'])
        install.rollback_engine(self.vault)
        self.assertEqual(engine.read_text(encoding='utf-8'), original)
        self.assertEqual(note.read_text(encoding='utf-8'), 'keep this source')

    def test_rollback_rejects_later_edits_before_writing_any_file(self):
        install.upgrade(self.vault)
        engine = self.vault / 'engine/beyin.py'
        launcher = self.vault / 'engine/Beyin.cmd'
        launcher.write_bytes(launcher.read_bytes() + b'REM later edit\n')
        before = engine.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Rollback conflict'):
            install.rollback_engine(self.vault)
        self.assertEqual(engine.read_bytes(), before)

    def test_legacy_install_needs_explicit_review_when_baseline_unknown(self):
        state = self.vault / '.state/installation.json'
        data = json.loads(state.read_text(encoding='utf-8'))
        data.pop('managed_engine_sha256')
        state.write_text(json.dumps(data), encoding='utf-8')
        engine = self.vault / 'engine/beyin.py'
        engine.write_text('# legacy engine', encoding='utf-8')
        self.assertIn('engine/beyin.py', install.upgrade_plan(self.vault)['conflicts'])
        with self.assertRaises(ValueError):
            install.upgrade_plan(self.vault, accepted=['PROFILE.md'])

    def test_rollback_rejects_backup_tampering(self):
        result = install.upgrade(self.vault)
        backup = Path(result['backup'])
        manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
        Path(manifest[0]['backup']).write_text('corrupt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            install.rollback_engine(self.vault)

    def test_upgrade_and_rollback_refuse_active_worker(self):
        with install.beyin.lock(self.vault / '.state/worker.lock'):
            with self.assertRaisesRegex(ValueError, 'Worker busy'):
                install.upgrade(self.vault)
            with self.assertRaisesRegex(ValueError, 'Worker busy'):
                install.rollback_engine(self.vault)

    def test_rollback_rejects_manifest_pointing_outside_backup(self):
        result = install.upgrade(self.vault)
        backup = Path(result['backup'])
        manifest_path = backup / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest[0]['backup'] = str(self.vault / 'PROFILE.md')
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Invalid engine rollback source'):
            install.rollback_engine(self.vault)
