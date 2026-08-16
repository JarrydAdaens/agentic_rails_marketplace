# Changelog — codex-as-critic-guardrail (Claude Code host)

Keep this file and `VERSION` in sync with `PLUGIN_VERSION` in
`lib/critic_consult.py`. This tree carries only the Claude Code host; the
Cursor host is a separate copy under `plugins/cursor/`.

## 1.2.0 — 2026-08-16

- Remove MCP entirely. Claude Code now consults through the same shell CLI
  transport the Cursor host already used (`cli/consult_critic.py`), unlocked
  on `PostToolUse` matcher `Bash` instead of an MCP tool name.
- Delete `.mcp.json` and `mcp/`.
- Collapse `docs/hosts/` into a single `docs/architecture.md` now that this
  tree serves one host.

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
