# codex-as-advisor-guardrail (Claude Code host)

Cross-vendor actor-advisor guardrail for **Claude Code**. The executor must
consult a constructive, read-only advisor at decision points, and the
session's first write is gated while the advisor is healthy and no consult has
succeeded yet. The advisor backend is the local **Codex CLI** (not the Codex
IDE). Prefer this plugin when you want a capability lift and forward paths for
the executor, not an antagonistic second opinion.

The Cursor host of this same guardrail is a separate copy under
`plugins/cursor/codex-as-advisor-guardrail/`; the two share no code or
manifest.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_advisor.py` (stdin JSON) | `PostToolUse` matcher `Bash` | **No** |

Architecture: [docs/architecture.md](docs/architecture.md). Version history:
[CHANGELOG.md](CHANGELOG.md).

## Harness config

Optional project file (JSONC — `//` comments allowed):

```jsonc
{
  "model": "gpt-5.6-sol",
  "effort": "high",
  "fast": false,
  "consult_timeout_seconds": 1800,
  "health_timeout_seconds": 90
}
```

Path: `harness/codex-as-advisor-guardrail/config.json`. Create it with the
user-invoked skill **`codex-advisor-init`**. Missing file → built-in defaults.
Invalid file → health goes offline (gate disarmed). Env vars
`CODEX_ADVISOR_TIMEOUT_SECONDS` / `CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS` override
the matching timeout fields when set.

## Skills

| Skill | Purpose |
| --- | --- |
| `codex-advisor-help` | What the plugin does, hooks, when the gate fires |
| `codex-advisor-init` | Write the commented harness config |
| `codex-advisor-health` | Mid-session ONLINE/OFFLINE retest |

## Health and self-disable

On session start the plugin probes Codex with the configured model (short
timeout, default 90s via `CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS`).

| Health | Write gate |
| --- | --- |
| pending | Allow (fail-open; Cursor sessionStart is fire-and-forget) |
| online | Deny until a successful consult |
| offline | Allow; status explains why |

Retest mid-session with the user-invoked skill **`codex-advisor-health`**
(`disable-model-invocation: true`) or `cli/advisor_health.py`. A successful
consult also marks the session online.

## Timeouts

| Cap | Default | Config field | Env override |
| --- | --- | --- | --- |
| Consult | 1800s | `consult_timeout_seconds` | `CODEX_ADVISOR_TIMEOUT_SECONDS` |
| Health probe | 90s | `health_timeout_seconds` | `CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS` |

Precedence: env (if set) → harness config → built-in default.

## Runtime

Python-only launcher: `scripts/launch.py` (no `.cmd`). Cursor hooks call
`uv run --no-project python ./scripts/launch.py …`. Requires `uv` or a working
`python` on PATH; optional `AGENTIC_RAILS_UV` override.

## Choosing between codex-as-critic and codex-as-advisor

Both gate the first write behind a consult when healthy. Prefer the **critic**
when the failure mode is same-family groupthink and you want an antagonistic
second opinion. Prefer the **advisor** when you want constructive plans, course
corrections, and completion verdicts for a smaller or less experienced executor.

## Known limitations

- Shell writes are ungated by design.
- Gating is per session; long multi-task sessions force only the first consult
  while online.
- The advisor sees the structured payload and the readable workspace, not the
  executor transcript.
- Requires authenticated Codex CLI access to the configured model and consumes
  Codex quota.
