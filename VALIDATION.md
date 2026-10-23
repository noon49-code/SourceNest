# Validation scope

Engine 1.4.1 includes the fix for Codex AgentMessage content blocks with type Text and provider-neutral transcript adapters. It also keeps summary and source-backed memory extraction in separate model roles. Local alias-aware Markdown search, bounded query context and processing profiles are covered by synthetic tests. The regression fixture preserves the observed event shape with synthetic message text.

The local suite covers replay, incremental append, incomplete tails, long-message splitting, both conversation roles, Claude/Cursor/normalized transcript envelopes, prompt-hook fallback, tool/reasoning exclusion, evidence validation, proposal/decision distinction, project isolation, worker locks, failure queues, budget/auth pause, immutable source checks, deterministic wiki links, Codex/Claude integration merging and safe upgrade behavior. Setup and verification wrappers are exercised separately with temporary paths.

Before preparing this public package, Windows + Codex CLI 0.154.0-alpha.6.2 was live-tested with gpt-5.6-luna: startup context, automatic user/assistant capture, background summary and source hashes passed. The split extraction path is covered by synthetic provider tests; the default gpt-5.6-sol extraction account still needs to be available to each user. Those private test files are not shipped. This is not a claim that every Codex version or model account is compatible.

The public installer and source package are tested separately with temporary fake integration directories and no model calls. Existing vaults can be upgraded or connected through reversible paths, which are covered by the same file logic. See tests/test_public_install.py. Run all tests with python -m unittest discover -s tests -v.

Not live-verified here: other operating systems, other model providers, Claude's running application, forced interruption/compaction lifecycle events, and all desktop UI session variants. Claude settings are generated from the documented hook shape; Cursor and other tools still depend on the export format they expose.


## Unreleased V3 workflow adaptation — 2026-10-23

43 synthetic tests passed, including managed-file upgrade conflicts, explicit legacy-file review, engine rollback, checksum corruption, backup path escape, active worker refusal, local sync and readable diagnostics. Python compilation and `git diff --check` passed. No live provider calls or private vault migration were used for this validation.


## SourceNest 2.0 — 2026-10-23

81 synthetic offline tests passed on Windows / Python 3.11. Python compilation and git diff whitespace validation passed. This includes the previous evidence/model-role suite and new verified package build/update/rollback/recovery, corruption and path attacks, legacy engine migration, runtime state and budget preservation, note privacy/readback, companion conflicts, shared-budget advisor scoring and Laya credential/checkpoint/truncation gates.

Generated OpenCode and OMP JavaScript passed Node syntax checks. OpenCode context delivery, Hermes callbacks, Kiro plain-text bridging and two distinct hook subprocess sessions were exercised against synthetic project data. The fresh-setup subprocess used an explicit temporary external state directory. No private vault, real provider, API key, model weight or native GUI trust state was used.

The Windows/macOS/Linux GitHub Actions matrix passed all 81 tests on Python 3.11 and 3.13: [verified run](https://github.com/noon49-code/SourceNest/actions/runs/39945595965). Native client versions, actual Jev/Laya service responses and a real user-opened assistant session remain live validation steps. Synthetic session receipts prove the test delivery path, not the factual correctness of an assistant answer.

The release also preserves the earlier deployed provenance audit and one bounded extraction-only evidence repair. Added regression tests verify repair uses the extractor role, consumes the shared budget, detects changed sources and rejects paraphrased quotations.

A Windows upgrade of an existing private vault was then verified with doctor, audit and review: configuration, registry, source events, compiled records, notes and generated views remained byte-identical. Existing model roles, runtime location and budgets were preserved; the optional advisor remained off. No backlog processing or provider call was performed during the upgrade.

The initial remote matrix exposed equivalent-path handling on macOS (/var versus /private/var) and Windows short temporary paths. Note creation/readback now canonicalizes the vault root; a regression fixture covers equivalent path spellings. Runtime migration assertions compare canonical destinations.
