# Changelog

## Unreleased

- Support an optional `temporary_budget` with a timezone-aware `until` timestamp.
  Workers check expiry before every job and fall back to normal call limits.
  The spent-call counter is preserved. Preferences and doctor show effective limits.

## 1.4.1 — keep processing after invalid evidence

- Keep rejected source/evidence jobs in the queue while processing independent jobs.
- After three failures, hold the affected job for review; `process --retry` retries it explicitly.
- Expose the held-job count as `doctor.needs_review`. Source and quote validation remain strict.

## 1.4.0 — local search and processing profiles

- Add bounded, project-scoped Markdown search with optional human-maintained topic aliases.
- Allow `context --query` to include local search results without a model call.
- Add Normal, Economical and Manual processing profiles while preserving the summary/extraction model roles.
- Report the active profile from `doctor` and keep the new controls in the portable vault config.

## 1.3.0 — separate summary and memory extraction models

- Use the configured Luna model only for a neutral session synopsis.
- Use a separate stronger extractor model for source-backed decisions, preferences,
  corrections and tasks.
- Keep the legacy single-model configuration as a compatibility fallback.

## 1.2.0 — easier Windows setup

- Add `setup.ps1` and `setup.cmd` wrappers with Python and assistant-home discovery.
- Add automatic new-install versus existing-vault upgrade selection.
- Add read-only `--verify` reporting for the vault, hooks and memory instruction files.

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
