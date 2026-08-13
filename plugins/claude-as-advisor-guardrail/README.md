# claude-as-advisor-guardrail

Cross-vendor advisor guardrail for Codex and Cursor. It launches the locally
authenticated Claude Code CLI as a constructive, read-only advisor and gates
the lead session's first write until `consult_advisor` completes.

The launcher uses `--model opus --effort high`. Anthropic defines `opus` as the
latest Opus alias, so it selects Opus 5 when that model is available without
pinning the plugin to a dated model ID. The nested session runs in safe mode,
plan permission mode, and with only `Read`, `Grep`, and `Glob` tools.

| Lead IDE | Adapter |
| --- | --- |
| Codex | Bundled MCP and trusted Codex lifecycle hooks |
| Cursor | Native Cursor MCP and hooks |
| Claude Code | Not offered; use `local-advisor-guardrail` |

For Cursor, install through `/plugin` or Customize → Marketplace, approve the
MCP server, and start a fresh session. For Codex, install the plugin, enable its
MCP server, review the bundled hooks with `/hooks`, and start a new thread.
Both adapters fail open with a diagnostic until their matching MCP server has
been listed for the current workspace.

Requirements: authenticated `claude` CLI and Python 3. Cursor on Windows also
requires PowerShell. Override the 600-second timeout with
`CLAUDE_ADVISOR_TIMEOUT_SECONDS`.
