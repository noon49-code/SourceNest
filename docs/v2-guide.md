# SourceNest 2.0 — independent portable memory

SourceNest 2.0 independently implements the capabilities listed in the [adaptation matrix](avenox-v3-adaptation.md). It does not embed or run the Avenox engine. Python 3.11+ is required; Git is optional for local checkpoints. No pip packages, model weights or background server are installed.

## Fresh installation: Windows, macOS, Linux

Use `python` on Windows or `python3` on macOS/Linux. The same commands work with either executable. Select a **private vault outside the SourceNest source repository**, and an existing project directory:

```text
python setup.py --vault /absolute/private-vault --workspace /absolute/project --project demo --client codex --client claude
python setup.py --vault /absolute/private-vault --workspace /absolute/project --project demo --client codex --client claude --apply
```

Preview is the default. `--apply` creates a new vault or uses the verified package transaction to upgrade an existing vault. Add `--client kiro`, `antigravity`, `opencode`, `omp` or `hermes` to select those integrations. The installer never grants trust. Choose only the clients you actually use; native plugins require their host application.

Runtime locks, counters, cursors, advisor settings and recovery journals live outside the vault. The defaults are LocalAppData/SourceNest on Windows, Library/Application Support/SourceNest on macOS, and XDG_STATE_HOME/sourcenest (or ~/.local/state/sourcenest) on Linux, with a separate directory per canonical vault path. Use `--state /absolute/local-state` to override. Cloud-sync destinations are rejected. `.sourcenest-runtime.json` is machine-local and must not be synced.

Existing direct `install.py` integrations remain supported. Existing vaults retain their state location unless explicitly migrated. Stop assistant clients and workers before running:

```text
python beyin.py state-migrate --path /absolute/local-state
```

Migration verifies copied counters/cursors before switching the pointer and retains old files for inspection. The queue and source records remain in the private vault. It does not reset call budgets.

The installer creates the platform update shortcut: `Beyni Guncelle.cmd`, `Beyni Güncelle.command`, or `Beyni Güncelle.sh` plus a Linux desktop launcher. macOS/Linux may require allowing execution; Linux desktop shells may require explicitly trusting the launcher. Python installation and operating-system permission decisions remain with the user.

## New projects and clients

Register each project once, then install selected project-local hooks there:

```text
python beyin.py register --project demo --path /absolute/project --name Demo
python beyin.py clients plan --workspace /absolute/project --client opencode --client kiro
python beyin.py clients install --workspace /absolute/project --client opencode --client kiro
```

Client install preserves unrelated JSON hooks, AGENTS.md text and CLAUDE.md content. A missing CLAUDE.md imports AGENTS.md; an existing import does not get a duplicate memory block. Modified SourceNest skills/plugins cause a conflict instead of being overwritten. The generated three SourceNest skills are mirrored for Kiro.

| Client | Generated integration | Manual step |
| --- | --- | --- |
| Codex | `.codex/hooks.json` | Review/trust hooks in Codex; restart session |
| Claude Code | `.claude/settings.local.json` | Review normal workspace/hook trust; restart |
| Kiro | `.kiro/hooks/sourcenest.json`, mirrored skills | Review Agent Hooks or CLI `/hooks`; restart |
| Antigravity | SourceNest namespace in `.agents/hooks.json` | Review normal workspace trust |
| OpenCode | `.opencode/plugins/sourcenest.js`, 1.x and 2.x entry points | Open the registered workspace; plugin auto-loads |
| OMP | `.omp/hooks/pre/sourcenest.ts` | Open the registered workspace; hook auto-loads |
| Hermes | `.sourcenest/adapters/hermes/` | Link/copy this directory into the correct Hermes profile's plugins directory, run `hermes plugins enable sourcenest`, restart |

Codex/Claude preserve their transcript capture adapters. Other integrations deliver bounded project context and capture user prompts when a session ID is provided; they do not claim a full assistant transcript if the host does not provide one. Use `capture-file` for supported exports and `note-create` for source notes. Child sessions are skipped by the native adapters when the host exposes parent/session-init metadata. No client trust hash is synthesized.

Client setup is its own reversible transaction, scoped to that workspace:

```text
python beyin.py clients rollback --workspace /absolute/project
python beyin.py clients recover --workspace /absolute/project
```

`recover` restores an interrupted setup. `rollback` undoes the last completed setup. Later user edits cause a refusal before any restoration writes.

## Structured notes, sync and separate-process readback

Prepare a local JSON file, for example `example-note.json`:

```json
{"project":"demo","title":"Database choice","slug":"database-choice","body":"Use SQLite for the local prototype.","aliases":["storage"],"visibility":"private","remote_allowed":false}
```

```text
python beyin.py note-create --file /absolute/example-note.json
python beyin.py sync --project demo
python beyin.py context --project demo --query storage --json
```

The retrieved record reports its `source`, `id` and current `source_sha256`. `note-create` writes only to that project's `notes/` or `knowledge/` directory, refuses to overwrite a different existing note, and defaults to private/local-only. It uses a JSON metadata comment in Markdown; unmarked manually written Markdown is treated as private/local-only. No model call is needed for creation, sync or local context.

Sync regenerates views from existing records and indexes note metadata. It does not turn unprocessed transcripts into memories or bypass invalid evidence.

### Companion identity

```text
python beyin.py companion status
python beyin.py companion setup --file /absolute/user-answers.json
```

The answers JSON accepts only `name`, `address_as`, and `preferences`. Ask the user at most three short questions before preparing it. No values are invented. Existing Core.md/Soul.md candidates produce `needs_attention` instead of a second identity folder; the source is not overwritten. Identity context stays local and is bounded when delivered to a registered project.

### Actual cross-session verification

After note creation and separate-command readback, open a **new client session in the registered project** and ask about the saved topic. If automatic hook context is unavailable, run `context` and `sync` directly rather than claiming hook success. The command below reports current-hash note deliveries to distinct hook sessions:

```text
python beyin.py verify-session --project demo --record RECORD_ID
```

Two recorded session deliveries are necessary for `verified: true`; this proves recorded delivery only. A human must still verify the assistant's answer. Synthetic subprocess tests are not a substitute for a real new client session.

## Verified updates, complete managed rollback and recovery

```text
python beyin.py update --check
python beyin.py update
python beyin.py rollback
python beyin.py recover
```

The updater finds the latest stable release in **noon49-code/SourceNest**, requires `SourceNest-X.Y.Z.zip` and its `.sha256` asset, verifies SHA-256, then validates the archive and each manifest entry. API rate limits fall back to the official stable-release redirect. A network error never means "up to date". Network updates require the new assets to have been published; old releases without them return an explicit error.

For an offline update, provide a verified package plus its adjacent `.sha256`, or pass an explicit checksum file:

```text
python beyin.py update --check --package /absolute/SourceNest-2.0.0.zip
python beyin.py update --package /absolute/SourceNest-2.0.0.zip
```

Archive members are read in memory after validating paths, duplicates, symlinks, size limits and file hashes; they are never blindly extracted. Downloaded installer scripts are never executed. Packages cannot manage user configuration, profiles, project sources or records. Modified managed files produce conflicts. Legacy files without a baseline require a reviewed migration through `install.py --upgrade --plan` and exact per-file acceptance; no global overwrite switch exists.

The worker lock serializes maintenance against processing. An external transaction journal saves prior content before writes. `rollback` restores/removes **all managed files changed by the last package transaction**, including modules, launcher, version marker and applicable shortcut, while preserving later user edits through conflict checks. `recover` returns an interrupted transaction to its prior state. Both validate backup checksums before writing. User notes, config, budgets and separately installed client settings are outside a package transaction; client settings have their own rollback/recover commands above. The older `install.py --rollback-engine` remains an engine-only compatibility command.

## Optional Jev / Laya advisor

The advisor starts **off**. It never creates or approves memories. Luna remains the neutral-summary model; the configured stronger model still extracts decisions, preferences, corrections and tasks. Advisor scoring is a separate role.

```text
python beyin.py jev status --human
python beyin.py jev shadow
python beyin.py context --project demo --query storage --jev
python beyin.py jev on
python beyin.py jev off
```

Use an environment variable `TYPESAFE_API_KEY`; never pass a key as an argument, note, or chat message. The optional local `jev.json` in runtime state accepts an absolute `env_file`. Status reports only whether a key was loaded. `shadow` scores but preserves local order; `on` may reorder eligible sources. Errors, absent keys, invalid responses and changed sources fall back to local retrieval. Raw queries, source text, keys and provider error bodies are not logged or cached; cached scores are tied to the complete request and source hash.

Each HTTP attempt reserves a call from the **same daily budget** used by the memory worker. Candidate counts are also bounded by the per-run cap. Claims batches that exceed that cap are rejected. Advisor calls are not unlimited retries.

Only notes explicitly marked `internal` or `public` **and** `remote_allowed: true` can be sent. Private notes, `sensitivity: sensitive`, project mismatches, stale hashes and local secret-pattern matches are excluded. Pattern matching cannot identify every secret; metadata must be set intentionally. Source hashes are checked again after calls. Complete note context is required within size bounds; oversize sources fall back rather than silently losing qualifications.

Automatic per-turn advisory context is a separate opt-in:

```text
python beyin.py jev shadow --enable auto_context
python beyin.py jev on --enable auto_context
python beyin.py jev on --disable auto_context
```

This may send each prompt and eligible source text to the configured provider. Keep it off unless that data flow is intended. `SOURCENEST_ADVISOR_DISABLE=1`, compatibility variable `BEYIN_JEV_DISABLE=1`, or a runtime `jev.disabled` file disables calls without erasing the saved mode.

Laya is an **already separately installed** loopback service. SourceNest does not install PyTorch, Laya or weights:

```text
python beyin.py jev shadow --provider laya
python beyin.py jev status --check
```

The default endpoint is `http://127.0.0.1:8765`. Only numeric loopback addresses are accepted; proxies and redirects are disabled. TypeSafe credentials are never sent to Laya; `LAYA_API_KEY` is optional. Laya remains shadow-only, supports `multilingual`/`english`, and rejects wrong checkpoints, truncated responses and overlarge inputs. The health check sends no notes and does not contact TypeSafe.

`jev-review` / `jev-memory` take a JSON object with `claim` and 1–8 `evidence` entries (`record_id`, `source_sha256`, exact `quote`). `jev-answer` accepts 1–20 objects with `text` and `citations` in the same evidence format, subject to the per-run cap. Review checks the original local source and keeps `approved: false`, `memory_written: false`, and `route: inspect_sources`. Scores are advice, never authority to accept a proposal or change a stored decision.

## Local controls and health

```text
python beyin.py doctor --human
python beyin.py audit
python beyin.py review
python beyin.py preferences --interval 30 --human
python beyin.py preferences --profile manual
```

Local automatic checks are throttled inside the open application's hook activity. No operating-system scheduler wakes a closed application. Manual mode disables automatic processing. Diagnostics flag a stored counter above the current cap without resetting it. A clean source audit does not prove model interpretation, live provider access or native-client compatibility.

## Validation boundary

Offline fixtures cover all command families, package attacks/recovery, privacy and budget gates, generated JavaScript syntax, client callback contracts, and cross-process delivery. Windows is the local test host. The repository CI matrix checks Windows/macOS/Linux. Native GUI trust prompts, actual client versions and live Jev/Laya responses must be checked in the corresponding installed application/service before claiming end-to-end support there.
