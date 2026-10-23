# Changelog

## 2.0.0 — 2026-10-23

- Independently implement stable SourceNest release discovery, bounded verified package reading,
  SHA-256 validation, managed update transactions, complete managed rollback and crash recovery.
- Add cross-platform setup, OS-local runtime state with explicit verified migration, platform shortcuts,
  an update/source release builder, and a Windows/macOS/Linux test workflow.
- Add reversible project-local Codex, Claude, Kiro, Antigravity, OpenCode 1.x/2.x, OMP and Hermes integration generators.
- Add source-backed structured Markdown notes, local note lookup, companion onboarding and session delivery receipts.
- Add an off-by-default TypeSafe Jev/Laya advisor with source privacy gates, separate auto-context opt-in,
  conservative Laya shadow mode, source-bound score cache, safe diagnostics and shared call-budget reservations.
- Add queue review/audit, local check intervals and a diagnostic for counters exceeding the active daily cap.
- Preserve existing source/evidence validation and separate summary/extractor model roles.


- Adapt selected Avenox V3 workflow ideas independently: managed engine hash baselines,
  read-only upgrade preflight and per-file legacy/customization review.
- Add checksum-verified engine-only rollback; reject later edits and unsafe backup paths.
  Upgrade and rollback require the worker lock.
- Add `doctor --human`, `preferences --human`, and model-free `sync` for local generated views.
- Document adoption scope and limitations in `docs/avenox-v3-adaptation.md`.


- Prefer Codex desktop's current `CODEX_CLI_PATH` over an older `codex` wrapper on `PATH`.
  This keeps worker calls and `doctor` on the same authenticated CLI.
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
