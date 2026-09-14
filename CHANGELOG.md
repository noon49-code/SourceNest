# Changelog

## 1.1.2 — resilient Windows launcher

- Keep the bundled Codex runtime fallback in `Beyin.cmd` before trying `python.exe` on PATH.

## 1.1.1 — safe existing-vault upgrade

- Add `--upgrade` to update managed engine files while preserving project data and user configuration.
- Allow a single upgrade to connect Codex, Claude Code, or both, with a dated rollback manifest.

## 1.1.0 — portable assistant integrations

- Add Claude Code lifecycle hooks and user-level `CLAUDE.md` memory instructions.
- Add Cursor and normalized JSONL transcript adapters plus `capture-file`.
- Add upgrade and integration-only installer paths for existing vaults.
- Keep the vault schema, source links and summarizer choices independent of the assistant client.

## 1.0.1 — public source package

- Accept current Codex Text blocks in assistant messages.
- Separate public software from private runtime vault files.
- Add empty registry and preference templates, English and Turkish setup documentation, MIT license and credits.
- Include synthetic regression tests; exclude private live transcripts and reports.
