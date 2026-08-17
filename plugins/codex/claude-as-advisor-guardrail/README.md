# claude-as-advisor-guardrail (Codex host)

Cross-vendor advisor guardrail for **Codex**. It launches the locally
authenticated Claude Code CLI as a constructive, read-only advisor via a shell
CLI transport. This host has no confirmed hook mechanism in this repository
— no `.codex-plugin/plugin.json` here or elsewhere wires a `hooks` key — so
this tree is **consult-capable but not gate-enforcing**: run the CLI manually
before writing rather than relying on a write to be blocked.

The launcher uses `--model opus --effort high`. Anthropic defines `opus` as the
latest Opus alias, so it selects Opus 5 when that model is available without
pinning the plugin to a dated model ID. The nested session runs in safe mode,
plan permission mode, and with only `Read`, `Grep`, and `Glob` tools.

The Cursor host of this same guardrail is a separate copy under
`plugins/cursor/claude-as-advisor-guardrail/`; unlike this tree, it has a
proven hook path and does enforce the gate.

| How to consult | Enforced? | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_advisor.py` (stdin JSON) | **No** — run manually | **No** |

Requirements: authenticated `claude` CLI and `uv`. Override the 600-second
timeout with `CLAUDE_ADVISOR_TIMEOUT_SECONDS`.
