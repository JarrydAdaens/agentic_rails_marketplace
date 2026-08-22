# Changelog — codex-as-advisor-guardrail (Cursor host)

## 1.2.0 — 2026-08-22

- Add project-persisted enabled state and hooks that early-out completely when
  the advisor is disabled.
- Add model/effort, consult timeout, and installed-version skills. The picker
  supports GPT-5.6 Sol/Terra/Luna, GPT-5.5, GPT-5.4, and GPT-5.4 Mini plus
  Low through Ultra effort.
- Make health report JSONC config presence and path; retain `fast` as a legacy
  advanced config field.

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json` and
`PLUGIN_VERSION` in `lib/advisor_consult.py`. This tree carries only the
Cursor host; the Claude Code host is a separate copy under `plugins/claude/`.

## 1.1.1 — 2026-08-16

- Docs only: collapse `docs/hosts/` into a single `docs/architecture.md` and
  drop references to the Claude Code MCP transport, now that this tree serves
  one host and Claude Code's own copy has moved to a shell CLI transport too.

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
