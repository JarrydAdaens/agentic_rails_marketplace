# Architecture — codex-as-advisor-guardrail (Claude Code host)

Cross-vendor guardrail: **executor host** is Claude Code; the **advisor
backend** is the Codex CLI. Plugin name `codex-as-*` names the backend, not a
Codex IDE host (there is no `.codex-plugin/` in this tree).

## Layout

| Path | Role |
| --- | --- |
| `lib/` | Shared consult, config, health, session markers, Windows PATH restore |
| `cli/consult_advisor.py` | Shell transport (stdin JSON) |
| `cli/advisor_health.py` | Health retest CLI |
| `cli/advisor_init.py` | Write commented harness config |
| `skills/codex-advisor-health/` | User-invoked retest skill |
| `skills/codex-advisor-init/` | User-invoked config init skill |
| `skills/codex-advisor-help/` | User-invoked help skill |
| `hooks/hooks.json` | Claude Code hook wiring |
| `scripts/launch.py` | Cross-platform Python launcher |

## Gate state machine

Per-session markers in the system temp directory:

1. **pending** — health not finished → writes allowed
2. **online** — probe ok → deny writes until consult marker
3. **offline** — probe/consult hard failure → writes allowed + offline message

## Host: Claude Code

- Registration: `.claude-plugin/plugin.json` (no MCP manifest)
- Hooks: `hooks/hooks.json`
- Consult: Shell → `uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py` with stdin JSON
- Unlock: `PostToolUse` matcher `Bash`, command containing `consult_advisor`
- Launcher: `python -c` + `CLAUDE_PLUGIN_ROOT` (platform-agnostic)

## Transport

Calls `lib/advisor_consult.consult()` → `codex exec --ephemeral` with harness
`model` / `effort` / optional `service_tier=fast`.
