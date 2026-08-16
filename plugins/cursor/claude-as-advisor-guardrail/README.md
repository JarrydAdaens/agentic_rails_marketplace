# claude-as-advisor-guardrail (Cursor host)

Cross-vendor advisor guardrail for **Cursor**. It launches the locally
authenticated Claude Code CLI as a constructive, read-only advisor and gates
the session's first write until `consult_advisor.py` completes.

The launcher uses `--model opus --effort high`. Anthropic defines `opus` as the
latest Opus alias, so it selects Opus 5 when that model is available without
pinning the plugin to a dated model ID. The nested session runs in safe mode,
plan permission mode, and with only `Read`, `Grep`, and `Glob` tools.

The Codex host of this same guardrail is a separate copy under
`plugins/codex/claude-as-advisor-guardrail/`; it has no confirmed Codex hook
mechanism to enforce a gate, so it is consult-capable but not enforcing. This
Cursor tree is the one that actually gates writes.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_advisor.py` (stdin JSON) | `afterShellExecution` | **No** |

Install through `/plugin` or Customize → Marketplace and start a fresh
session; no MCP server approval step is needed.

Requirements: authenticated `claude` CLI and `uv`. The plugin restores Windows
user and machine PATH values from the registry, recognizes WinGet's UV shim,
and resolves the absolute Claude CLI shim without operator PATH changes.
`AGENTIC_RAILS_UV` is optional and there is no direct-Python fallback.
Override the 600-second timeout with `CLAUDE_ADVISOR_TIMEOUT_SECONDS`.
