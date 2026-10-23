# Avenox V3 capability adaptation — SourceNest 2.0

Source reviewed: https://avenox.lol/beyin.md and the official Avenox v3.12.0 package/documentation, 23 October 2026. The reference ZIP was checksum-verified before inspection. This update is an independent SourceNest implementation; no Avenox runtime is bundled or installed. Existing SourceNest model-role and source-evidence contracts remain in place.

| Requested missing capability | Independent implementation | Validation |
| --- | --- | --- |
| Latest stable release discovery/download | `maintenance.latest_release`, official repository assets, API-rate-limit redirect fallback | Offline release/host/tag fixtures |
| SHA-256 and safe ZIP handling | Bounded in-memory archive validation, manifest hashes, traversal/duplicate/symlink rejection | Attack fixtures and actual built release package |
| Complete managed update rollback | Transaction stores all changed managed modules, launcher, shortcut and version metadata | Update/noop/rollback/content and counter preservation fixtures |
| Interrupted update recovery | `recover`, pre-write journal, checksum and later-edit conflicts | Simulated power-loss and backup corruption tests |
| Cross-platform setup and shortcuts | `setup.py`, native state roots, Windows/macOS/Linux shortcuts | Windows local execution; CI passed on all three platforms with Python 3.11 and 3.13 |
| External local runtime state | Explicit pointer and verified migration, original files retained | Counter/cursor preservation and path rejection tests |
| Seven assistant integrations | Codex, Claude, Kiro, Antigravity, OpenCode 1.x/2.x, OMP, Hermes | Generated configuration, JavaScript syntax, callback/subprocess fixtures; native application verification remains separate |
| Companion identity/onboarding | `companion status/setup`, three questions, existing Core/Soul conflict handling | Empty/user-supplied/conflicting identity fixtures |
| Structured note creation | `note-create --file`, project-local notes/knowledge, idempotent refusal to overwrite | Source integrity, metadata and path tests |
| Local refresh and retrieval | `sync`, `context --project --query --json`, source paths/hashes | Separate-process readback |
| New-session delivery verification | Bounded source-hash receipts and `verify-session` | Two independent hook subprocesses; real new application session still required |
| Optional Jev/Laya advisor | Off/shadow/on, TypeSafe and Laya SystemOne protocol, Laya shadow-only | Fake transport, provider/key separation, source-change and invalid-response tests |
| Advisor privacy and opt-ins | Private/sensitive/remote-disabled filters, explicit auto_context, kill switch, no-text logs/cache | No-network and leakage-boundary fixtures |
| Local automatic controls | `preferences --interval`, manual mode, hook-driven throttle; no OS scheduler | Existing profile tests and bounded local implementation |

Implementation scope is the capabilities listed above, not byte-for-byte replication of every feature in the evolving Avenox product. SourceNest keeps its per-project vault and transcript compilation model. Advisor scoring does not replace the stronger memory extractor, approve memories, resolve contradictions or assert facts. Full managed-package rollback and per-workspace client rollback have explicit, separate transaction boundaries.

See [the complete setup, update, privacy and verification guide](v2-guide.md). Unsupported runtime access, missing release assets and network failures return errors rather than success. Native client trust approval and provider activation remain separate user actions. An existing private vault can retain its runtime location and all model/budget settings during upgrade.
