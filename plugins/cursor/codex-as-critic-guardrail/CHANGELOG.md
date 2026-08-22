# Changelog — codex-as-critic-guardrail (Cursor host)

## 1.2.1 — 2026-08-22

- Toast on sessionStart after the project config loads, using PowerShell's
  registered App User Model ID. Disabled projects (`enabled: false`) stay silent.

## 1.2.0 — 2026-08-22

- Add project-persisted enabled state and hooks that early-out completely when
  the critic is disabled.
- Add model/effort, consult timeout, and installed-version skills. The picker
  supports GPT-5.6 Sol/Terra/Luna, GPT-5.5, GPT-5.4, and GPT-5.4 Mini plus
  Low through Ultra effort.
- Make health report JSONC config presence and path; retain `fast` as a legacy
  advanced config field.

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json` and
`PLUGIN_VERSION` in `lib/critic_consult.py`. This tree carries only the
Cursor host; the Claude Code host is a separate copy under `plugins/claude/`.

## 1.1.1 — 2026-08-16

- Docs only: collapse `docs/hosts/` into a single `docs/architecture.md` and
  drop references to the Claude Code MCP transport, now that this tree serves
  one host and Claude Code's own copy has moved to a shell CLI transport too.

## 1.1.0 — 2026-08-14

- Cursor consult transport is Shell CLI only (no Cursor MCP); Claude Code keeps
  MCP `consult_critic`.
- Shared `lib/` for config, consult, health, and session markers; harness JSONC
  at `harness/codex-as-critic-guardrail/cursor-config.json`.
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
