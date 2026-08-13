# local-advisor-guardrail

A portable local advisor gate for Claude Code, Codex, and Cursor. “Local” means
the advisor is a child agent launched inside the same agentic IDE and account
as the executor—not a cross-vendor critic or remote advisory service. Each host
must complete one structured consultation before its first write in a session.

| Host | Local advisor | Invocation |
| --- | --- | --- |
| Claude Code | Opus, high effort | `local-advisor-guardrail:advisor` native subagent |
| Codex | GPT-5.6 Sol, high reasoning | `consult_advisor` MCP tool launching a child `codex exec` |
| Cursor | Cursor Grok 4.5 High | `consult_advisor` MCP tool launching a child `agent` session |

Claude Code uses the bundled read-only subagent. Codex and Cursor use the same
bundled stdio MCP server with a host argument; that server launches the current
IDE's own CLI in read-only/ask mode. Claude Code and Codex models are fixed.
Cursor defaults to `cursor-grok-4.5-high`; a successful `consult_advisor` call
may supply a different exact Cursor model ID, which is remembered per project
in `harness/local-advisor-guardrail/config.json`.

The hooks inject `advisor-protocol.md`, deny the first write until a consult,
and mark the session after the matching subagent or MCP tool completes. Cursor
uses `preToolUse`, `afterMCPExecution`, `sessionStart`, and its native response
schemas. Its gate covers `Write`, `StrReplace`, `Delete`, and compatible legacy
edit names. The gate activates only after Cursor has registered the live MCP
server; hook, payload, or server failures allow the write and return an
actionable diagnostic instead of deadlocking the session.

## Cursor installation

Adding this repository with `agent plugin marketplace add` only registers the
catalog. Install `local-advisor-guardrail` separately through Cursor's
interactive `/plugin` Marketplace screen or **Customize → Marketplace**, select
project or user scope, and approve the MCP server. Editing
`.cursor/settings.json` does not install a missing plugin. A successful install
creates a cache entry and exposes
`plugin-local-advisor-guardrail-local-advisor-guardrail:consult_advisor` in a
fresh Agent session.

The Cursor MCP launcher is rooted with `${PLUGIN_ROOT}` and uses the bundled
PowerShell launcher, so it does not depend on Cursor choosing the plugin as its
working directory or on a bare `python` command. The launcher honors
`AGENTIC_RAILS_PYTHON`, then tries `py.exe`, `python`, and `uv`.

Markers live under `<temp>/local-advisor-guardrail-markers/`. Markers from the
former `advisor-guardrail`, `advisor-codex-guardrail`, and legacy Claude setup
are recognized during migration and cleared at session start.

## Requirements

- Claude Code: plugin agents and hooks with `model: opus` and `effort: high`.
- Codex: the `codex` CLI authenticated with access to `gpt-5.6-sol`.
- Cursor: the `agent` CLI authenticated with access to
  `cursor-grok-4.5-high`.
- Windows PowerShell plus Python 3 through `AGENTIC_RAILS_PYTHON`, `py.exe`,
  `python`, or `uv` for Cursor hooks and MCP; Python 3 for other hosts.

## Migration

Claude Code migrates `advisor-guardrail` through the marketplace rename map.
Codex and Cursor users should remove the old plugin identity and install
`local-advisor-guardrail`; legacy session markers remain compatible.

## Known limitations

- Shell writes are advisory-only; reliably classifying arbitrary shell
  commands is outside this gate.
- Gating is per session, not per task.
- MCP-launched local advisors receive the structured payload and readable
  workspace, not the executor's entire transcript.
