# SourceNest

## Pick up a project without retelling its history

SourceNest is project memory for Codex on Windows. It captures new user and assistant messages from registered projects and compiles decisions, preferences, corrections, and open work into Markdown pages with links to the source messages.

One private vault holds a separate folder for each project. The vault lives outside your code repositories. JSON records and Markdown pages remain readable when you change models; another assistant app still needs its own capture integration.

[Install](#install-powershell) · [Türkçe rehber](README.tr.md) · [Validation](VALIDATION.md) · [Privacy](PRIVACY.md)

**Current scope:** early release, tested automatic integration with Windows + Codex CLI. Summaries currently use Turkish. The configured summarizer receives captured text, so local file storage does not mean offline processing.

![SourceNest data flow: Codex session to source record, validated memory, and project wiki](docs/architecture.svg)

| When you need to… | SourceNest keeps… |
| --- | --- |
| pick up a project after a break | the project status, index, and durable context |
| remember why a choice was made | a dated record with a source message and quote |
| move from Luna to another model | the same portable records and Markdown views |
| work across several repositories | separate memory selected by the project path |

Each extracted item links to a source message and quote. Those checks help you trace a claim; they do not prove that the model interpreted it correctly.

### The path from a conversation to a page

<details>
<summary>Detailed capture and summarization flow</summary>

~~~mermaid
flowchart TD
    A[Codex session] -->|visible user and assistant text| B[Lifecycle hooks]
    B --> C[Immutable JSON event]
    C --> D[Configured model provider]
    D -->|structured JSON| E[Local validation]
    E --> F[Project records]
    F --> G[Markdown topic wiki]
    F --> H[Daily log and decisions]
~~~

</details>

The model proposes structured data. Local code checks the source IDs, evidence quotes, and schema before anything reaches the generated wiki.

[Türkçe kurulum ve kullanım](README.tr.md) · [Privacy](PRIVACY.md) · [Credits](CREDITS.md) · [MIT license](LICENSE)

## Status

Early release, engine 1.0.1. Windows + Codex CLI is the tested automatic integration. Python 3.11+ and Git are required. No third-party Python dependencies.

The engine was live-tested with Codex CLI 0.154.0-alpha.6.2 and `gpt-5.6-luna`. The default model must be available to your own account; change `summarizer.model` in the installed vault's `config.json` if needed. CLI flags and hook formats can change between releases. Markdown summaries and engine messages currently use Turkish.

## How it works

1. Register a project directory once.
2. SessionStart supplies that project's status and index, plus shared preferences.
3. Stop, PreCompact, SessionEnd and Interrupt hooks capture new visible user/assistant text.
4. A background summarizer returns structured JSON. Local code validates evidence quotes, source IDs and schema.
5. Deterministic rendering creates a topic wiki, daily records and decision history.

Source text cannot choose output paths. Assistant proposals cannot become user decisions solely on assistant evidence. Quote validation does not prove that an interpretation is correct. Memory is historical data, never new authorization.

## Install (PowerShell)

Download and extract the repository, then open PowerShell in the extracted folder. Ensure `python`, `git` and `codex` are available and `codex login status` reports a working login.

Choose a **new, private vault folder outside this repository**. Installation refuses to overwrite an existing vault.

```powershell
python --version
git --version
codex --version
codex login status
$BeyinVault = Join-Path $env:USERPROFILE 'Documents\Beyin'
$BeyinCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --registry projects.example.json
```

This prints the installation plan. To apply it:

The example registry is empty. Installation connects no projects until you run the registration command below. If `python` is unavailable but `py -3 --version` reports Python 3.11 or newer, use `py -3` in place of `python` throughout these commands.

```powershell
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --registry projects.example.json --apply
```

The installer merges five hooks into the user hooks file and adds a scoped memory block to AGENTS.md (or an existing nonempty AGENTS.override.md). Existing integration files are backed up inside the private vault. It does not change hook trust. In interactive `codex`, open `/hooks`, review the five commands pointing to your vault, and trust them. Start a fresh session in a registered project.

## Register a project

Replace the example with an existing directory:

```powershell
python "$BeyinVault\engine\beyin.py" register --project my-project --path 'D:\Projects\MyProject' --name 'My Project'
python "$BeyinVault\engine\beyin.py" doctor
```

Project IDs use lowercase ASCII letters, digits and hyphens. Paths determine the project; unrelated chats are excluded. Existing history is not bulk-imported on installation. On first attachment to a resumed session, the cursor skips earlier history.

## Commands

```powershell
python "$BeyinVault\engine\beyin.py" context --cwd 'D:\Projects\MyProject'
python "$BeyinVault\engine\beyin.py" ingest --project my-project --file 'D:\Documents\Research.md' --title 'Research'
python "$BeyinVault\engine\beyin.py" process --retry
python "$BeyinVault\engine\beyin.py" rebuild --project my-project
python "$BeyinVault\engine\beyin.py" pause
python "$BeyinVault\engine\beyin.py" resume
```

`pause` disables automatic capture; it does not terminate an already running worker. `resume` re-enables capture; use `process --retry` to explicitly retry processing after fixing errors. `doctor` checks login, queue and worker health; it is not a live model test. PDF input must first be converted to text. URLs are source metadata, not automatic downloads.

## Where your memory lives

```text
Beyin/                         # private vault, outside the source repository
├── config.json                # model and call limits
├── projects.json              # registered project paths
├── PROFILE.md                 # shared preferences
└── projects/
    ├── my-project/
    │   ├── raw/               # captured events and imported sources
    │   ├── records/           # validated structured summaries
    │   ├── wiki/              # generated index and topic pages
    │   ├── daily/             # generated daily logs
    │   ├── STATUS.md
    │   ├── DECISIONS.md
    │   └── notes/             # your manually maintained notes
    └── another-project/       # separate project memory
```

The private vault contains `projects/<id>/raw`, `records`, `wiki`, `daily`, `STATUS.md`, `DECISIONS.md`, and `notes`. Put manual notes in `notes`; generated views are rebuilt by the engine. Keep separate backups: local Git checkpoints are not an off-device backup.

## Changing models and managing usage

The default summarizer uses your Codex account, with at most 4 calls per run and 20 per UTC day across the vault. These are call limits, not monetary limits. Errors retain queued work; processing resumes on later hooks or an explicit retry, not a timer. Memory context and summarization consume tokens.

Change `summarizer` in the installed `config.json` to select a model/provider. `codex_cli` is live-tested; `openai_responses` and an explicit local `command` adapter exist but are not live-verified across providers. API use requires its own environment credential and billing. The command adapter receives the prompt on stdin and must return the summary JSON schema on stdout; `{model}` arguments are substituted without shell evaluation.

Claude and normalized JSONL readers are covered by local tests, but automatic Claude integration is not installed. Switching apps requires its own capture integration. Files remain readable without any model.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests run in temporary directories and do not call a model. The existing engine was additionally tested with real Codex lifecycle capture, both conversation roles, background Luna summarization and source hashes. Private transcripts and live reports are deliberately excluded from this repository. See [VALIDATION.md](VALIDATION.md).

## Disable or remove

Run `pause` first. Remove only the five commands pointing to this vault from your user `hooks.json` and the `BEGIN BEYIN PORTABLE MEMORY` block from the relevant global AGENTS file. Preserve other hooks and instructions. Restart sessions. Backups under the vault's `.backups` are for inspection; restoring whole files could overwrite later unrelated edits. Your vault data remains available.

## Scope

No hosted service, telemetry, automatic cloud backup, embedding database or global conversation archive. Summaries can be incomplete or wrong, and abrupt termination may prevent capture. Protect the private vault and its Git history; publish only this source repository.

## Compatibility / Uyumluluk

SourceNest is the public project name. The engine retains the Beyin command names, default vault folder and hook markers for compatibility with existing installations.
