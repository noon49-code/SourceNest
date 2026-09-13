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
