# Changelog — codex-as-advisor-guardrail

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json` and
`PLUGIN_VERSION` in `lib/advisor_consult.py`.

## 1.1.0 — 2026-08-14

- Rebuild to match the codex-as-critic gold standard: shared `lib/` consult stack,
  Claude MCP + Cursor Shell CLI (no Cursor MCP), harness JSONC config, session
  health self-disable (`pending` / `online` / `offline`), Python-only
  `scripts/launch.py`.
- Add user-invoked skills: `codex-advisor-help`, `codex-advisor-health`,
  `codex-advisor-init`.
- Preserve the constructive advisor persona (plan / course correction /
  completion verdict) while sharing the critic's transport and gate design.
- Document version as `VERSION` + this changelog.

## Prior

Earlier releases used Cursor MCP packaging and lacked the help/init/health skill
trio and harness config layout introduced in 1.1.0.
