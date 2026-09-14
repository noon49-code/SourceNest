# Validation scope

Engine 1.1.1 includes the fix for Codex AgentMessage content blocks with type Text and provider-neutral transcript adapters. The regression fixture preserves the observed event shape with synthetic message text.

The local suite covers replay, incremental append, incomplete tails, long-message splitting, both conversation roles, Claude/Cursor/normalized transcript envelopes, prompt-hook fallback, tool/reasoning exclusion, evidence validation, proposal/decision distinction, project isolation, worker locks, failure queues, budget/auth pause, immutable source checks, deterministic wiki links and Codex/Claude integration merging.

Before preparing this public package, Windows + Codex CLI 0.154.0-alpha.6.2 was live-tested with gpt-5.6-luna: startup context, automatic user/assistant capture, background summary and source hashes passed. Those private test files are not shipped. This is not a claim that every Codex version or model account is compatible.

The public installer and source package are tested separately with temporary fake integration directories and no model calls. Existing vaults can be upgraded or connected through reversible paths, which are covered by the same file logic. See tests/test_public_install.py. Run all tests with python -m unittest discover -s tests -v.

Not live-verified here: other operating systems, other model providers, Claude's running application, forced interruption/compaction lifecycle events, and all desktop UI session variants. Claude settings are generated from the documented hook shape; Cursor and other tools still depend on the export format they expose.
