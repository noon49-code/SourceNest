# Assistant integrations

SourceNest separates **capture**, **summary** and **memory extraction**. Capture adapters turn an assistant's visible conversation into the same source-backed event format. A lightweight summary model writes a neutral synopsis, while a separate stronger model turns the same source events into validated decisions, preferences, corrections and tasks. This keeps the vault portable when you change from Codex to Claude Code, Cursor, or another model provider.

For a one-command Windows setup, run `setup.ps1` (or `setup.cmd`) from the extracted repository. It detects the bundled/runtime Python, the usual assistant homes and whether the vault needs a first install or an upgrade. It prints a plan by default; add `-Apply` to write it and `-Verify` to check it later.

## Codex and Claude Code

The installer can connect both clients in one pass:

```powershell
$BeyinVault = Join-Path $env:USERPROFILE 'Documents\Beyin'
$BeyinCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$BeyinClaudeHome = Join-Path $env:USERPROFILE '.claude'
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --claude-home "$BeyinClaudeHome" --registry projects.example.json --apply
```

Codex receives a `hooks.json` entry for `SessionStart`, `Stop`, `PreCompact`, `SessionEnd` and `Interrupt`. Claude Code receives a `settings.json` entry for `SessionStart`, `UserPromptSubmit`, `Stop`, `PreCompact` and `SessionEnd`. Both commands pass hook JSON on standard input to the same `engine/beyin.py` process.

Claude Code also reads the user-level `CLAUDE.md` file. SourceNest adds a bounded memory instruction there and preserves existing text. Its user settings and hook documentation are maintained by Anthropic; if a future Claude release changes the hook schema, update the adapter rather than changing the vault format.

For an existing vault, upgrade the managed engine and connect only the clients you want:

```powershell
python install.py --target "$BeyinVault" --claude-home "$BeyinClaudeHome" --upgrade
```

The upgrade command writes a dated manifest in `.backups`, replaces only managed engine files, and does not replace vault data or user configuration. Review the generated command in the client's settings before enabling it. The installer never changes trust or permission decisions. Use `--integrate` when the engine is already current and you only need to add a client later.

## Cursor and other JSONL tools

Tools that expose a JSONL transcript can use the normalized adapter without a new installer integration. A record can be as small as:

```json
{"role":"user","content":"Keep the database decision.","timestamp":"2026-09-14T10:30:00Z"}
{"role":"assistant","content":"I will preserve it in the migration notes.","timestamp":"2026-09-14T10:30:05Z"}
```

Capture an exported file into a registered project:

```powershell
python "$BeyinVault\engine\beyin.py" capture-file `
  --project my-project `
  --file 'D:\Exports\session.jsonl' `
  --adapter normalized `
  --session exported-session
```

Cursor-shaped records with `type`, `message.role` and `message.content` can use `--adapter cursor`. Claude-shaped JSONL records can be replayed with `--adapter claude`. The command keeps a byte cursor per session, skips incomplete trailing lines until the next run, and stores the original event before summarization.

## Tools without a transcript hook

There is no single hook standard shared by every AI assistant. Some desktop applications expose neither a conversation file nor lifecycle events. For those tools, export the session to the normalized JSONL shape or write a small bridge that sends the same records to `capture-file`. The project registry, source links, validation rules and Markdown wiki remain unchanged.

The two model roles are separate choices in `config.json`:

```json
{
  "summarizer": {
    "provider": "codex_cli",
    "model": "gpt-5.6-luna",
    "reasoning_effort": "low"
  },
  "extractor": {
    "provider": "codex_cli",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high"
  }
}
```

`summarizer` produces only a neutral synopsis. `extractor` alone classifies source-backed memory items such as decisions, preferences and corrections. If `extractor` is omitted, the engine uses the legacy single-model combined response for compatibility.

Both roles support these provider choices:

* `codex_cli` uses the installed Codex CLI account (the live-tested default).
* `openai_responses` uses an OpenAI API key from the configured environment variable.
* `command` sends the role-specific prompt to an explicitly configured local executable and expects the matching SourceNest JSON schema on standard output. This is the escape hatch for another CLI or a wrapper around Claude, Gemini, or a self-hosted model.

Do not pass raw transcripts as command-line arguments. The engine sends them on standard input, validates the returned evidence IDs and quotes, and never lets model output choose a file path.
