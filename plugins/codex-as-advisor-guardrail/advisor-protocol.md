# Codex Advisor Protocol

Use `consult_advisor` before substantive implementation, when stuck, before a
meaningful pivot, and before declaring completion. The first file write is
gated until one consultation completes.

Send all five fields: `task`, `stage`, `approach`, `evidence`, and `question`.
Valid stages are `planning`, `stuck`, `pivot-check`, and `completion-review`.
The advisor is constructive and read-only. It returns a plan, course correction,
or completion verdict from GPT-5.6 Sol at high reasoning.

In Cursor the qualified tool is
`plugin-codex-as-advisor-guardrail-codex-as-advisor-guardrail:consult_advisor`.
In Claude Code, call the `consult_advisor` tool from the plugin MCP server.
