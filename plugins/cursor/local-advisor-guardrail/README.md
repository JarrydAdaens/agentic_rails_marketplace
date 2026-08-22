# local-advisor-guardrail

A Cursor-native local advisor gate. “Local” means
the advisor is a custom child agent launched inside the same Cursor runtime and account
as the executor—not a cross-vendor critic or remote advisory service. Each host
must complete one structured consultation before its first write in a session.

| Host | Local advisor | Invocation |
| --- | --- | --- |
| Claude Code | Opus, high effort | `local-advisor-guardrail:advisor` native subagent |
| Codex | GPT-5.6 Sol, high reasoning | `consult_advisor` MCP tool launching a child `codex exec` |
| Cursor | Configured native Cursor subagent | Cursor Task/Agent delegation |

Cursor uses bundled read-only custom subagents—there is no MCP server and no
second `agent` CLI process. The project JSONC chooses Auto, Cursor Grok 4.6,
Composer 2.5, Gemini 3.7 Flash, GPT-5.4-Nano, or Kimi-K3. Cursor applies each
model's native effort defaults.

Its Cursor-only project config is
`harness/local-advisor-guardrail/cursor-config.json`. It intentionally does
not use a generic `config.json`, so this host cannot collide with a Claude or
Codex local-advisor configuration in the same harness directory.

The hooks inject `advisor-protocol.md`, deny the first write until a consult,
and mark the session after the matching native subagent completes. Cursor uses
`preToolUse`, `postToolUse`, `sessionStart`, and its native response schemas.
Its gate covers `Write`, `StrReplace`, `Delete`, and compatible legacy edit
names. Invalid configuration, hook, or payload failures allow the write and
return an actionable diagnostic instead of deadlocking the session.

## Cursor installation

Copy the plugin source into Cursor's local plugin directory and reload Cursor.
The bundle includes its custom agents under `agents/`; no marketplace or MCP
approval is required. Start a fresh Agent session so Cursor loads the hooks and
the selected `local-advisor-*` subagent.

Markers live under `<temp>/local-advisor-guardrail-markers/`. Markers from the
former `advisor-guardrail`, `advisor-codex-guardrail`, and legacy Claude setup
are recognized during migration and cleared at session start.

## Requirements

- Claude Code: plugin agents and hooks with `model: opus` and `effort: high`.
- Codex: the `codex` CLI authenticated with access to `gpt-5.6-sol`.
- Cursor: access to the configured Cursor model and the bundled custom-agent
  capability.
- Cursor: `uv` and Python 3 available to run the local hook scripts.

## Migration

Claude Code migrates `advisor-guardrail` through the marketplace rename map.
Codex and Cursor users should remove the old plugin identity and install
`local-advisor-guardrail`; legacy session markers remain compatible.

Cursor does not apply Claude's marketplace rename map to an already cached hook
bundle. Before enabling `local-advisor-guardrail`, uninstall or disable the old
`advisor-guardrail` entry through Cursor's `/plugin` screen (or **Customize →
Plugins**). Its historical Cursor hook used a bare Python command with
`failClosed: true` and can otherwise continue blocking writes from the cache.

## Known limitations

- Shell writes are advisory-only; reliably classifying arbitrary shell
  commands is outside this gate.
- Gating is per session, not per task.
- Native local advisors receive the structured protocol and readable workspace,
  not the executor's entire transcript.
