# Architecture — codex-as-critic-guardrail

Multi-host guardrail: **executor hosts** are Claude Code and Cursor; the
**critic backend** is the Codex CLI. Plugin name `codex-as-*` names the backend,
not a Codex IDE host (there is no `.codex-plugin/`).

## Layout

| Path | Role |
| --- | --- |
| `lib/` | Shared consult, config, health, session markers, Windows PATH restore |
| `mcp/critic_server.py` | Claude-only JSON-RPC MCP transport |
| `cli/consult_critic.py` | Cursor Shell transport (stdin JSON) |
| `cli/critic_health.py` | Health retest CLI |
| `cli/critic_init.py` | Write commented harness config |
| `skills/codex-critic-health/` | User-invoked retest skill |
| `skills/codex-critic-init/` | User-invoked config init skill |
| `skills/codex-critic-help/` | User-invoked help skill |
| `hooks/hooks.json` | Claude hook wiring |
| `hooks/cursor-hooks.json` | Cursor hook wiring |
| `scripts/launch.py` | Cross-platform Python launcher |

## Gate state machine

Per-session markers in the system temp directory:

1. **pending** — health not finished → writes allowed  
2. **online** — probe ok → deny writes until consult marker  
3. **offline** — probe/consult hard failure → writes allowed + offline message  

## Transports

Both transports call `lib/critic_consult.consult()` → `codex exec --ephemeral`
with harness `model` / `effort` / optional `service_tier=fast`.

See [hosts/claude.md](hosts/claude.md) and [hosts/cursor.md](hosts/cursor.md).
