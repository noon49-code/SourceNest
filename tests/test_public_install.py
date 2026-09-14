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
