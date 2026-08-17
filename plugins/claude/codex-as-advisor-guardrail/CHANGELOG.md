# Changelog — codex-as-advisor-guardrail (Claude Code host)

Keep this file and `VERSION` in sync with `PLUGIN_VERSION` in
`lib/advisor_consult.py`. This tree carries only the Claude Code host; the
Cursor host is a separate copy under `plugins/cursor/`.

## 1.2.0 — 2026-08-16

- Remove MCP entirely. Claude Code now consults through the same shell CLI
  transport the Cursor host already used (`cli/consult_advisor.py`), unlocked
  on `PostToolUse` matcher `Bash` instead of an MCP tool name.
- Delete `.mcp.json` and `mcp/`.
- Collapse `docs/hosts/` into a single `docs/architecture.md` now that this
  tree serves one host.

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
