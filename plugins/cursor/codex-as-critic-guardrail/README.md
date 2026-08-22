# codex-as-critic-guardrail (Cursor host)

Cross-vendor actor-critic guardrail for **Cursor**. The executor must consult
an antagonistic, read-only critic at decision points, and the session's first
write is gated while the critic is healthy and no consult has succeeded yet.
The critic backend is the local **Codex CLI** (not the Codex IDE).
Same-family models share blind spots; the critic exists to catch what the
executor's family would miss alone.

The Claude Code host of this same guardrail is a separate copy under
`plugins/claude/codex-as-critic-guardrail/`; the two share no code or
manifest.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_critic.py` (stdin JSON) | `afterShellExecution` | **No** |

Architecture: [docs/architecture.md](docs/architecture.md). Version history:
[CHANGELOG.md](CHANGELOG.md).

> Formerly published as `critic-guardrail`. Existing installs migrate through
> the marketplace `renames` map.

## Harness config

Optional project file (JSONC — `//` comments allowed):

```jsonc
{
  "enabled": true,
  "model": "gpt-5.6-sol",
  "effort": "high",
  "fast": false,
  "consult_timeout_seconds": 1800,
  "health_timeout_seconds": 90
}
```

Path: `harness/codex-as-critic-guardrail/cursor-config.json`. Create it with the
user-invoked skill **`codex-critic-init`**. Missing file → built-in defaults.
Invalid file → health goes offline (gate disarmed). Env vars
`CODEX_CRITIC_TIMEOUT_SECONDS` / `CODEX_CRITIC_HEALTH_TIMEOUT_SECONDS` override
the matching timeout fields when set.

## Skills

| Skill | Purpose |
| --- | --- |
| `codex-critic-help` | What the plugin does, hooks, when the gate fires |
| `codex-critic-init` | Write the commented harness config |
| `codex-critic-health` | Mid-session ONLINE/OFFLINE retest |
| `codex-critic-enabled` | Persistently engage or disengage the critic |
| `codex-critic-model` | View or persist model and reasoning effort |
| `codex-critic-timeout` | View or persist the full-consult timeout |
| `codex-critic-version` | Print installed version and edit timestamp |

## Health and self-disable

On session start the plugin probes Codex with the configured model (short
timeout, default 90s via `CODEX_CRITIC_HEALTH_TIMEOUT_SECONDS`).

| Health | Write gate |
| --- | --- |
| pending | Allow (fail-open; Cursor sessionStart is fire-and-forget) |
| online | Deny until a successful consult |
| offline | Allow; status explains why |

Retest mid-session with the user-invoked skill **`codex-critic-health`**
(`disable-model-invocation: true`) or `cli/critic_health.py`. A successful
consult also marks the session online.

## Timeouts

| Cap | Default | Config field | Env override |
| --- | --- | --- | --- |
| Consult | 1800s | `consult_timeout_seconds` | `CODEX_CRITIC_TIMEOUT_SECONDS` |
| Health probe | 90s | `health_timeout_seconds` | `CODEX_CRITIC_HEALTH_TIMEOUT_SECONDS` |

Precedence: env (if set) → harness config → built-in default.

## Runtime

Python-only launcher: `scripts/launch.py` (no `.cmd`). Cursor hooks call
`uv run --no-project python ./scripts/launch.py …`. Requires `uv` or a working
`python` on PATH; optional `AGENTIC_RAILS_UV` override.

## Choosing between local-advisor and codex-as-critic

Both gate the first write behind a consult when healthy. Prefer the critic when
the failure mode is same-family groupthink; prefer an advisor when you want a
capability lift for a smaller executor.

## Known limitations

- Shell writes are ungated by design.
- Gating is per session; long multi-task sessions force only the first consult
  while online.
- The critic sees the structured payload and the readable workspace, not the
  executor transcript.
- Requires authenticated Codex CLI access to the configured model and consumes
  Codex quota.
