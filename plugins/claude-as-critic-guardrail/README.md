# claude-as-critic-guardrail

Cross-vendor critic guardrail for Codex and Cursor. It launches the locally
authenticated Claude Code CLI as an adversarial, read-only reviewer and gates
the lead session's first write until `consult_critic` completes.

The launcher uses `--model opus --effort high`. Anthropic defines `opus` as the
latest Opus alias, so it selects Opus 5 when available without pinning a dated
model ID. The nested session uses safe mode, plan permission mode, and only the
`Read`, `Grep`, and `Glob` tools.

| Lead IDE | Adapter |
| --- | --- |
| Codex | Bundled MCP and trusted Codex lifecycle hooks |
| Cursor | Native Cursor MCP and hooks |
| Claude Code | Not offered; use a local Claude critic workflow |

For Cursor, install through `/plugin`, approve the MCP server, and start a new
session. For Codex, install the plugin, enable its MCP server, trust its hooks
through `/hooks`, and start a new thread. Both adapters fail open until the
matching MCP server is live for the current workspace.

Requirements: authenticated `claude` CLI and Python 3 for Codex. On Cursor,
the plugin restores Windows user and machine PATH values from the registry,
recognizes WinGet's UV shim, and resolves the absolute Claude CLI shim without
operator PATH changes. `AGENTIC_RAILS_UV` is optional and there is no
direct-Python fallback. Override the 600-second timeout with
`CLAUDE_CRITIC_TIMEOUT_SECONDS`.
