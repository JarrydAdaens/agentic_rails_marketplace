---
name: codex-critic-help
description: >-
  Explain the codex-as-critic-guardrail plugin: what it does, hosts (Claude vs
  Cursor), harness config, health/offline behavior, skills, and which hooks fire
  when. Use when the user asks how the critic works or when to expect the write
  gate.
disable-model-invocation: true
---

# Codex critic help

Answer from this document. Start by running `python ./cli/critic_version.py` from the installed plugin root and include its one-line version result. Do not invent hooks or MCP tools that are not listed.

## What it is

`codex-as-critic-guardrail` forces a coding agent to consult an antagonistic,
read-only **Codex CLI** critic before the session's first file write — but only
while the critic is **healthy (online)**. If health fails (auth, quota, bad
model, bad config), the write gate **disarms** for that session so the IDE is
not bricked.

- **Backend:** Codex CLI (`codex exec`), not the Codex IDE.
- **Hosts:** Claude Code (MCP) and Cursor (Shell CLI, no MCP).

## Skills (user-invoked)

| Skill | Purpose |
| --- | --- |
| `codex-critic-help` | This overview |
| `codex-critic-init` | Write `harness/codex-as-critic-guardrail/cursor-config.json` with commented defaults |
| `codex-critic-health` | Retest critic reachability mid-session; print ONLINE/OFFLINE + gate status |
| `codex-critic-enabled` | Persistently engage or disengage the critic for this project |
| `codex-critic-model` | View or persist the Codex model and reasoning effort |
| `codex-critic-timeout` | View or persist the critic consult timeout |
| `codex-critic-version` | Print the installed version and edit timestamp |
| `codex-critic-install-hooks` | Merge hooks into the Cursor CLI user hooks file |
| `codex-critic-remove-hooks` | Remove this plugin's user-hook entries |

## Harness config

Path: `harness/codex-as-critic-guardrail/cursor-config.json` (JSONC; `//` comments OK).

Fields: `enabled`, `model`, `effort`, `fast`, `consult_timeout_seconds`, `health_timeout_seconds`.

When `enabled` is `false`, registered hooks immediately allow events: no health
probe, protocol injection, critic consult, or write gate runs. Use
`/codex-critic-enabled disabled` or `/codex-critic-enabled enabled`.
Use `/codex-critic-model gpt-5.6-sol high`, `/codex-critic-model 2a`, or a
future model id. `/codex-critic-timeout` accepts `123`, `fourhundred`, or
`default`; with no argument it shows the current setting and waits for input.

Create it with `/codex-critic-init`. Env overrides for timeouts only:
`CODEX_CRITIC_TIMEOUT_SECONDS`, `CODEX_CRITIC_HEALTH_TIMEOUT_SECONDS`.

## When the guardrail goes off (write gate)

The gate runs on **file write/edit tools**, not on Shell.

| Health state | First Write / StrReplace / Delete / Edit… |
| --- | --- |
| **pending** (health still running) | Allowed (fail-open) |
| **online** and no successful consult yet | **Denied** until a consult succeeds |
| **online** and consult already done | Allowed |
| **offline** | Allowed; message says critic is offline |

Expect a deny when: session health finished **online**, you have not consulted
yet this session, and the agent tries to write/edit a file.

You will **not** get a deny for: reads, greps, shell commands, or any write while
pending/offline.

## Hooks by host

### Cursor (`hooks/cursor-hooks.json`)

| Hook | When | What happens |
| --- | --- | --- |
| `sessionStart` | New Agent/composer chat | Cleanup stale markers; run health probe; inject protocol + presence status |
| `preToolUse` (Write\|StrReplace\|Delete\|Edit\|…) | Before those tools | Allow or deny per health + consult marker |
| `afterShellExecution` (command matches `consult_critic`) | After a successful Shell consult CLI | Mark session consulted (unlocks writes) |

Cursor consult transport: pipe JSON to `cli/consult_critic.py` (see protocol).
There is **no** Cursor MCP server for this plugin.

Run `/codex-critic-install-hooks` after copying the plugin into Cursor local
plugins. It merges absolute hook commands into `~/.cursor/hooks.json`, which
Cursor CLI loads for a fresh session. Use `/codex-critic-remove-hooks` to
remove only this plugin's entries.

### Claude Code (`hooks/hooks.json`)

| Hook | When | What happens |
| --- | --- | --- |
| `SessionStart` | New session | Cleanup; health; inject protocol + presence |
| `PreToolUse` (Write\|Edit\|…) | Before those tools | Allow or deny per health + consult marker |
| `PostToolUse` (`.*consult_critic$`) | After MCP `consult_critic` | Mark session consulted |

Claude consult transport: MCP tool `consult_critic`.

## Mid-session re-enable

If offline (or after fixing quota/auth/config in a long compacted thread), run
`/codex-critic-health`. ONLINE arms the gate again (next write needs a consult).

## Related files in the plugin

- `critic-protocol.md` — injected consult contract
- `docs/hosts/cursor.md` / `docs/hosts/claude.md` — host details
- `README.md` — short overview
