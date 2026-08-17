# Architecture — codex-as-critic-guardrail (Cursor host)

Cross-vendor guardrail: **executor host** is Cursor; the **critic backend**
is the Codex CLI. Plugin name `codex-as-*` names the backend, not a Codex IDE
host (there is no `.codex-plugin/` in this tree).

## Layout

| Path | Role |
| --- | --- |
| `lib/` | Shared consult, config, health, session markers, Windows PATH restore |
| `cli/consult_critic.py` | Shell transport (stdin JSON) |
| `cli/critic_health.py` | Health retest CLI |
| `cli/critic_init.py` | Write commented harness config |
| `skills/codex-critic-health/` | User-invoked retest skill |
| `skills/codex-critic-init/` | User-invoked config init skill |
| `skills/codex-critic-help/` | User-invoked help skill |
| `hooks/cursor-hooks.json` | Cursor hook wiring |
| `scripts/launch.py` | Cross-platform Python launcher |

## Gate state machine

Per-session markers in the system temp directory:

1. **pending** — health not finished → writes allowed
2. **online** — probe ok → deny writes until consult marker
3. **offline** — probe/consult hard failure → writes allowed + offline message

## Host: Cursor

- Registration: `.cursor-plugin/plugin.json` (**no** `mcpServers`)
- Hooks: `hooks/cursor-hooks.json`
- Consult: Shell → `uv run --no-project python ./scripts/launch.py ./cli/consult_critic.py` with stdin JSON
- Unlock: `afterShellExecution` matcher containing `consult_critic`
- Health retest: skill `codex-critic-health` or `cli/critic_health.py`

Cursor CLI MCP instantiation is unreliable; this host deliberately avoids MCP.
SessionStart is fire-and-forget, so health starts **pending** (writes allowed)
until the probe finishes.

## Transport

Calls `lib/critic_consult.consult()` → `codex exec --ephemeral` with harness
`model` / `effort` / optional `service_tier=fast`.
