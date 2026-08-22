---
name: claude-advisor-help
description: >-
  Explain the claude-as-advisor-guardrail plugin: what it does, hosts, harness
  config, health/offline behavior, skills, and which hooks fire when. Use when
  the user asks how the Claude advisor works or when to expect the write gate.
disable-model-invocation: true
---

# Claude advisor help

Answer from this document. Start by running `python ./cli/advisor_version.py` from
the installed plugin root and include its one-line version result. Do not invent
hooks or MCP tools that are not listed.

## What it is

`claude-as-advisor-guardrail` forces a coding agent from another vendor to
consult a constructive, read-only **Claude** advisor before the session's first
file write — but only while the advisor is **healthy (online)**. If health fails
(auth, quota, bad model, bad config), the write gate **disarms** for that
session so the IDE is not bricked.

- **Backend:** the locally authenticated Claude Code CLI (`claude -p`), run in
  safe mode, plan permission mode, with only `Read`, `Grep`, and `Glob`.
- **Hosts:** Cursor (Shell CLI, no MCP) enforces the gate. The Codex copy of
  this plugin is consult-capable only — no Codex hook mechanism is confirmed, so
  it has no gate, no health probe, and no skills.

## Skills (user-invoked)

| Skill | Purpose |
| --- | --- |
| `claude-advisor-help` | This overview |
| `claude-advisor-init` | Write `harness/claude-as-advisor-guardrail/cursor-config.json` with commented defaults |
| `claude-advisor-health` | Retest advisor reachability mid-session; print ONLINE/OFFLINE + gate status |
| `claude-advisor-enabled` | Persistently engage or disengage the advisor for this project |
| `claude-advisor-model` | Persist the advisor model and reasoning effort for this project |
| `claude-advisor-timeout` | View or persist the advisor consult timeout for this project |
| `claude-advisor-version` | Print the installed version and edit timestamp |

## Harness config

Path: `harness/claude-as-advisor-guardrail/cursor-config.json` (JSONC; `//` comments OK).

Fields: `enabled`, `model`, `effort`, `consult_timeout_seconds`, `health_timeout_seconds`.
`effort` is one of `low`, `medium`, `high`, `xhigh`, `max`. There is no `fast`
field — the Claude CLI has no fast-tier flag.

When `enabled` is `false`, the registered hooks still receive their events but
immediately allow them: no health probe, protocol injection, advisor consult,
or write gate runs. Use `/claude-advisor-enabled disabled` or
`/claude-advisor-enabled enabled` rather than editing the JSONC by hand.
Use `/claude-advisor-model opus high`, `/claude-advisor-model 2b`, or a future
model id such as `/claude-advisor-model deity high` to persist model and effort.
Use `/claude-advisor-timeout 123`, `/claude-advisor-timeout fourhundred`, or
`/claude-advisor-timeout default` to update the consult timeout. With no
argument, it explains the current setting and waits for your response.

Create it with `/claude-advisor-init`. A missing file is not an error; the
plugin falls back to built-in defaults (`opus`, `high`, 600s, 90s). Env
overrides for timeouts only: `CLAUDE_ADVISOR_TIMEOUT_SECONDS`,
`CLAUDE_ADVISOR_HEALTH_TIMEOUT_SECONDS`.

## When the guardrail goes off (write gate)

The gate runs on **file write/edit tools**, not on Shell.

| Health state | First Write / StrReplace / Delete / Edit… |
| --- | --- |
| **pending** (health still running) | Allowed (fail-open) |
| **online** and no successful consult yet | **Denied** until a consult succeeds |
| **online** and consult already done | Allowed |
| **offline** | Allowed; message says the advisor is offline |

Expect a deny when: session health finished **online**, you have not consulted
yet this session, and the agent tries to write/edit a file.

You will **not** get a deny for: reads, greps, shell commands, or any write
while pending/offline.

## Hooks (Cursor — `hooks/cursor-hooks.json`)

| Hook | When | What happens |
| --- | --- | --- |
| `sessionStart` | New Agent/composer chat | Cleanup stale markers; run health probe; inject protocol + presence status |
| `preToolUse` (Write\|StrReplace\|Delete\|Edit\|…) | Before those tools | Allow or deny per health + consult marker |
| `afterShellExecution` (command matches `consult_advisor`) | After a successful Shell consult CLI | Mark session consulted (unlocks writes) |

Consult transport: pipe JSON to `cli/consult_advisor.py` (see the protocol).
There is **no** MCP server for this plugin on any host.

## Mid-session re-enable

If offline (or after fixing quota/auth/config in a long compacted thread), run
`/claude-advisor-health`. ONLINE arms the gate again, clearing any earlier
consult marker, so the next write needs a fresh consult.

## Related files in the plugin

- `advisor-protocol.md` — injected consult contract
- `README.md` — short overview and requirements
- `CHANGELOG.md` — what changed per version
