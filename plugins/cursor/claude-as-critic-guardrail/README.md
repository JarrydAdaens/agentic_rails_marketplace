# claude-as-critic-guardrail (Cursor host)

Cross-vendor critic guardrail for **Cursor**. It launches the locally
authenticated Claude Code CLI as an adversarial, read-only reviewer and gates
the session's first write until `consult_critic.py` completes.

The launcher uses `--model opus --effort high`. Anthropic defines `opus` as the
latest Opus alias, so it selects Opus 5 when available without pinning a dated
model ID. The nested session uses safe mode, plan permission mode, and only the
`Read`, `Grep`, and `Glob` tools.

The Codex host of this same guardrail is a separate copy under
`plugins/codex/claude-as-critic-guardrail/`; it has no confirmed Codex hook
mechanism to enforce a gate, so it is consult-capable but not enforcing. This
Cursor tree is the one that actually gates writes.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_critic.py` (stdin JSON) | `afterShellExecution` | **No** |

Install through `/plugin` or Customize → Marketplace and start a fresh
session; no MCP server approval step is needed.

Requirements: authenticated `claude` CLI and `uv`. The plugin restores Windows
user and machine PATH values from the registry, recognizes WinGet's UV shim,
and resolves the absolute Claude CLI shim without operator PATH changes.
`AGENTIC_RAILS_UV` is optional and there is no direct-Python fallback.
Override the 600-second timeout with `CLAUDE_CRITIC_TIMEOUT_SECONDS`.
