# codex-as-advisor-guardrail

Cross-vendor advisor guardrail for Claude Code and Cursor. It gives either lead
IDE a constructive second opinion from the authenticated local Codex CLI and
gates the session's first write until `consult_advisor` completes.

The advisor runs `gpt-5.6-sol` with high reasoning in Codex's read-only sandbox.
It receives a structured task summary and may inspect the consumer workspace,
but it cannot modify files and does not receive the executor's transcript.

## Compatibility

| Lead IDE | Adapter |
| --- | --- |
| Claude Code | Claude plugin hooks plus bundled stdio MCP |
| Cursor | Native Cursor hooks plus cwd-independent stdio MCP |
| Codex | Not offered; use `local-advisor-guardrail` for a Codex child advisor |

Cursor users must install the plugin through `/plugin` or Customize →
Marketplace, approve the MCP server, and begin a fresh session. Merely adding
`enabled: true` to settings does not install it. The Cursor write gate fails
open with a diagnostic until Cursor has listed the live MCP server, preventing
a missing server from deadlocking all edits.

Install multiple consultation plugins only when multiple independent consults
are intentional; every installed gate must be satisfied.

Requirements: authenticated `codex` CLI and Python 3 for Claude Code. The
Cursor adapter requires `uv` in a standard per-user location or identified by
`AGENTIC_RAILS_UV`; it never falls back to a global Python command. Set
`CODEX_ADVISOR_TIMEOUT_SECONDS` to override the default 600-second consultation
timeout.
