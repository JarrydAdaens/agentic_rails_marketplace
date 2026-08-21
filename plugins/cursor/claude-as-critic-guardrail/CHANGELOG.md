# Changelog — claude-as-critic-guardrail (Cursor host)

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json`. This
tree carries only the Cursor host; the Codex host is a separate copy under
`plugins/codex/` and is consult-capable rather than gate-enforcing.

## 1.2.0 — 2026-08-20

- Add the `lib/` layer this plugin never had: harness JSONC config
  (`harness/claude-as-critic-guardrail/config.json` — `model`, `effort`,
  `consult_timeout_seconds`, `health_timeout_seconds`), session health markers,
  and a bounded health probe.
- Replace the unconditional write gate with the three-state health model
  (`pending` / `online` / `offline`) already used by `codex-as-*`: a session
  whose critic cannot be reached disarms the gate instead of blocking work.
- Add user-invoked skills `claude-critic-help`, `claude-critic-health`, and
  `claude-critic-init`, matching the `codex-as-critic-guardrail` trio.
- Add `cli/critic_health.py` and `cli/critic_init.py` behind those skills.
- Drive the consult model and effort from config instead of the hardcoded
  `opus` / `high` pair; those remain the defaults.
- Adopt the fuller `windows_runtime.py` (uv discovery, `AGENTIC_RAILS_UV`
  override) already shipping in `codex-as-critic-guardrail`.
- Add `tests/`, including a BOM-prefixed payload regression for the gate.

## 1.1.0 — Prior

Shell-CLI consult transport (no MCP), BOM-tolerant hook stdin, and a write gate
that denied until a consult succeeded with no health probe behind it.
