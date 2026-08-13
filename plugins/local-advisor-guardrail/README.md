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
IDE's own CLI in read-only/ask mode. Model selection is fixed by the plugin so
the executor cannot silently weaken its advisor.

The hooks inject `advisor-protocol.md`, deny the first write until a consult,
and mark the session after the matching subagent or MCP tool completes. Cursor
uses its native camel-case hook events and response schema; Claude Code and
Codex use the compatible `PreToolUse` schema.

Markers live under `<temp>/local-advisor-guardrail-markers/`. Markers from the
former `advisor-guardrail`, `advisor-codex-guardrail`, and legacy Claude setup
are recognized during migration and cleared at session start.

## Requirements

- Claude Code: plugin agents and hooks with `model: opus` and `effort: high`.
- Codex: the `codex` CLI authenticated with access to `gpt-5.6-sol`.
- Cursor: the `agent` CLI authenticated with access to
  `cursor-grok-4.5-high`.
- Python 3 on `PATH` for hook and MCP scripts.

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
