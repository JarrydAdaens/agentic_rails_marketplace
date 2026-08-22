# claude-as-critic-guardrail (Cursor host)

Cross-vendor critic guardrail for **Cursor**. It launches the locally
authenticated Claude Code CLI as an adversarial, read-only critic and gates the
session's first write until `consult_critic.py` completes — while the critic
is reachable.

The nested session runs in safe mode, plan permission mode, and with only
`Read`, `Grep`, and `Glob` tools. It defaults to `--model opus --effort high`.
Anthropic defines `opus` as the latest Opus alias, so it selects Opus 5 when
that model is available without pinning the plugin to a dated model ID.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| Shell → `cli/consult_critic.py` (stdin JSON) | `afterShellExecution` | **No** |

## Health self-disable

`sessionStart` runs a bounded health probe against the configured model. The
write gate follows its verdict:

| Health state | First Write / Edit / StrReplace / Delete |
| --- | --- |
| `pending` (probe still running) | Allowed — fail-open |
| `online`, no consult yet | **Denied** until one consult succeeds |
| `online`, consult done | Allowed |
| `offline` (auth, quota, model, config) | Allowed, with the reason |

A broken critic therefore costs you the guardrail, not your session. Retest
mid-session with the `claude-critic-health` skill; an ONLINE verdict re-arms
the gate.

## Skills

| Skill | Purpose |
| --- | --- |
| `claude-critic-help` | What the plugin does, hosts, hooks, gate behavior |
| `claude-critic-init` | Write the harness config with commented defaults |
| `claude-critic-health` | Retest reachability; print ONLINE/OFFLINE + gate status |
| `claude-critic-enabled` | Persistently engage or disengage the critic |
| `claude-critic-model` | Persist the critic model and reasoning effort |
| `claude-critic-timeout` | View or persist the full-consult timeout |
| `claude-critic-version` | Print the installed version and edit timestamp |

## What the consuming project provides

Nothing is required. Optionally, `harness/claude-as-critic-guardrail/config.json`
(JSONC — `//` comments allowed), written by `claude-critic-init`:

| Field | Default | Notes |
| --- | --- | --- |
| `model` | `opus` | Claude alias or full model id |
| `effort` | `high` | One of `low`, `medium`, `high`, `xhigh`, `max` |
| `consult_timeout_seconds` | `600` | Env override: `CLAUDE_CRITIC_TIMEOUT_SECONDS` |
| `health_timeout_seconds` | `90` | Env override: `CLAUDE_CRITIC_HEALTH_TIMEOUT_SECONDS` |

A missing file is a silent skip to those defaults; a malformed one takes the
critic offline with the parse error as the reason rather than failing the hook.

## Requirements and limitations

Install through `/plugin` or Customize → Marketplace and start a fresh session;
no MCP server approval step is needed.

Requires an authenticated `claude` CLI and `uv`. The plugin restores Windows
user and machine PATH values from the registry, recognizes WinGet's UV shim, and
resolves the absolute Claude CLI shim without operator PATH changes.
`AGENTIC_RAILS_UV` is optional.

Shell commands are not gated, so an agent determined to route around the gate
can. The gate is a prompt for consultation, not a sandbox.

The Codex host of this same guardrail is a separate copy under
`plugins/codex/claude-as-critic-guardrail/`; it has no confirmed Codex hook
mechanism to enforce a gate, so it is consult-capable but not enforcing, and it
carries none of the health, config, or skill layers described above. This Cursor
tree is the one that actually gates writes.
