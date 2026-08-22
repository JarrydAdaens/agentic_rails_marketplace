---
name: codex-advisor-help
description: >-
  Explain the codex-as-advisor-guardrail plugin: what it does, hosts (Claude vs
  Cursor), harness config, health/offline behavior, skills, and which hooks fire
  when. Use when the user asks how the advisor works or when to expect the write
  gate.
disable-model-invocation: true
---

# Codex advisor help

Answer from this document. Start by running `python ./cli/advisor_version.py` from the installed plugin root and include its one-line version result. Do not invent hooks or MCP tools that are not listed.

## What it is

`codex-as-advisor-guardrail` forces a coding agent to consult a constructive,
read-only **Codex CLI** advisor before the session's first file write — but only
while the advisor is **healthy (online)**. If health fails (auth, quota, bad
model, bad config), the write gate **disarms** for that session so the IDE is
not bricked.

- **Backend:** Codex CLI (`codex exec`), not the Codex IDE.
- **Hosts:** Claude Code (MCP) and Cursor (Shell CLI, no MCP).

## Skills (user-invoked)

| Skill | Purpose |
| --- | --- |
| `codex-advisor-help` | This overview |
| `codex-advisor-init` | Write `harness/codex-as-advisor-guardrail/cursor-config.json` with commented defaults |
| `codex-advisor-health` | Retest advisor reachability mid-session; print ONLINE/OFFLINE + gate status |
| `codex-advisor-enabled` | Persistently engage or disengage the advisor for this project |
| `codex-advisor-model` | View or persist the Codex model and reasoning effort |
| `codex-advisor-timeout` | View or persist the advisor consult timeout |
| `codex-advisor-version` | Print the installed version and edit timestamp |
| `codex-advisor-install-hooks` | Merge hooks into the Cursor CLI user hooks file |
| `codex-advisor-remove-hooks` | Remove this plugin's user-hook entries |

## Harness config

Path: `harness/codex-as-advisor-guardrail/cursor-config.json` (JSONC; `//` comments OK).

Fields: `enabled`, `model`, `effort`, `fast`, `consult_timeout_seconds`, `health_timeout_seconds`.

When `enabled` is `false`, registered hooks immediately allow events: no health
probe, protocol injection, advisor consult, or write gate runs. Use
`/codex-advisor-enabled disabled` or `/codex-advisor-enabled enabled`.
Use `/codex-advisor-model gpt-5.6-sol high`, `/codex-advisor-model 2a`, or a
future model id. `/codex-advisor-timeout` accepts `123`, `fourhundred`, or
`default`; with no argument it shows the current setting and waits for input.

Create it with `/codex-advisor-init`. Env overrides for timeouts only:
`CODEX_ADVISOR_TIMEOUT_SECONDS`, `CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS`.

## When the guardrail goes off (write gate)

The gate runs on **file write/edit tools**, not on Shell.

| Health state | First Write / StrReplace / Delete / Edit… |
| --- | --- |
| **pending** (health still running) | Allowed (fail-open) |
| **online** and no successful consult yet | **Denied** until a consult succeeds |
| **online** and consult already done | Allowed |
| **offline** | Allowed; message says advisor is offline |

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
| `afterShellExecution` (command matches `consult_advisor`) | After a successful Shell consult CLI | Mark session consulted (unlocks writes) |

Cursor consult transport: pipe JSON to `cli/consult_advisor.py` (see protocol).
There is **no** Cursor MCP server for this plugin.

Run `/codex-advisor-install-hooks` after copying the plugin into Cursor local
plugins. It merges absolute hook commands into `~/.cursor/hooks.json`, which
Cursor CLI loads for a fresh session. Use `/codex-advisor-remove-hooks` to
remove only this plugin's entries.

### Claude Code (`hooks/hooks.json`)

| Hook | When | What happens |
| --- | --- | --- |
| `SessionStart` | New session | Cleanup; health; inject protocol + presence |
| `PreToolUse` (Write\|Edit\|…) | Before those tools | Allow or deny per health + consult marker |
| `PostToolUse` (`.*consult_advisor$`) | After MCP `consult_advisor` | Mark session consulted |

Claude consult transport: MCP tool `consult_advisor`.

## Mid-session re-enable

If offline (or after fixing quota/auth/config in a long compacted thread), run
`/codex-advisor-health`. ONLINE arms the gate again (next write needs a consult).

## Related files in the plugin

- `advisor-protocol.md` — injected consult contract
- `docs/hosts/cursor.md` / `docs/hosts/claude.md` — host details
- `README.md` — short overview
