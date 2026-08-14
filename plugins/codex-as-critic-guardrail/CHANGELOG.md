# Changelog — codex-as-critic-guardrail

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json` and
`PLUGIN_VERSION` in `lib/critic_consult.py`.

## 1.1.0 — 2026-08-14

- Cursor consult transport is Shell CLI only (no Cursor MCP); Claude Code keeps
  MCP `consult_critic`.
- Shared `lib/` for config, consult, health, and session markers; harness JSONC
  at `harness/codex-as-critic-guardrail/config.json`.
- Session health self-disable (`pending` / `online` / `offline`) so a broken
  Codex backend cannot brick the IDE write path.
- User-invoked skills: `codex-critic-help`, `codex-critic-health`,
  `codex-critic-init`.
- Python-only `scripts/launch.py` (no Windows `.cmd` launcher).
- Align published version to 1.1.0 and track history via `VERSION` + this
  changelog (supersedes interim 1.2.1 package labels from the rebuild spike).

## Prior

Earlier marketplace builds used Cursor MCP and older launcher/hook packaging.
See git history on this plugin path for pre-1.1 detail.
