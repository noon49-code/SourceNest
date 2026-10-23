# Data flow and privacy

The public repository is software, not a personal vault. Install the vault elsewhere.

- Registered project paths select which active sessions can be captured. No bulk archive scan is performed.
- Visible user and assistant text is stored locally. System messages, reasoning and tool outputs are excluded by the adapters.
- A few common credential patterns are masked. This is not comprehensive secret or personal-data detection; do not include sensitive material in captured sessions.
- Source text and topic names are sent to the configured summary and extraction providers. By default both use the user's Codex account, with Luna receiving the synopsis prompt and the stronger extractor receiving the memory-item prompt. API or command-provider settings change this data flow.
- No credentials are bundled. The API adapter reads its credential from an environment variable. Codex credentials are managed by Codex itself.
- Raw records are preserved. Generated summaries include evidence references; their interpretation can still be wrong.
- Imported documents are copied byte-for-byte into `raw/sources` before redaction. Pattern masking applies to the extracted event text, not that original document copy.
- The private vault uses local Git checkpoints, which can retain older versions of information. Deleting a current file does not erase history or provider-side retention.
- There is no built-in telemetry, remote upload of the vault, encryption, automatic remote backup or guaranteed capture after a crash.

Do not publish vault directories, their .git history, project registries, profile preferences, queue/state, integration backups or live transcripts. The public .gitignore is a guardrail, not a guarantee. The installed vault intentionally uses a separate vault.gitignore so local private history can record memory.


## SourceNest 2.0 additions

Structured notes default to private and remote-disabled. Normal local lookup/sync and companion setup make no model calls. Explicit advisor requests require an enabled mode and eligible source metadata; auto-context is a separate opt-in. They may send prompts and complete bounded eligible note text to TypeSafe, or to the explicitly selected loopback Laya service. The daily worker budget also bounds advisor calls. Shadow mode still sends eligible data for scoring.

Runtime state may live outside the vault and must not be cloud-synced. It contains counters, cursors, score-only caches, no-text call metadata and maintenance backup content. Recovery journals can contain previous engine/client configuration, including local paths: keep the runtime directory private. `.sourcenest-runtime.json` pins this machine's state path.

Project-local client files can contain interpreter and vault paths. Review them before committing project changes; no installer or updater pushes to GitHub. The release builder uses an explicit source whitelist and never archives a working vault, Git metadata, local config, queues or transcripts. A SHA-256 sidecar detects corruption; its authenticity depends on obtaining both assets from the trusted official release over HTTPS.

Details and transaction boundaries: [2.0 guide](docs/v2-guide.md).
