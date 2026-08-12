# advisor-guardrail

A single portable advisor gate for Claude Code, Codex, and Cursor. Each host
must complete one structured consultation before its first write in a session.

| Host | Advisor | Invocation |
| --- | --- | --- |
| Claude Code | Opus, high effort | `advisor-guardrail:advisor` subagent |
| Codex | GPT-5.6 Sol, high reasoning | `consult_advisor` MCP tool |
| Cursor | Cursor Grok 4.5 High | `consult_advisor` MCP tool |

Claude Code uses the bundled read-only subagent. Codex and Cursor use the same
bundled stdio MCP server with a host argument, so model selection is fixed by
the plugin rather than left to the executor. The MCP advisors run their CLI in
read-only/ask mode and return advice; they do not edit files.

The hooks inject `advisor-protocol.md`, deny the first write until a consult,
and mark the session after the matching subagent or MCP tool completes. Cursor
uses its native camel-case hook events and response schema; Claude Code and
Codex use the compatible `PreToolUse` schema.

Markers live under `<temp>/advisor-guardrail-markers/`. Markers from the two
pre-consolidation plugins are recognized during migration and cleared at
session start.

## Requirements

- Claude Code: a version supporting plugin agents, hooks, `model: opus`, and
  `effort: high`.
- Codex: the `codex` CLI installed and authenticated with access to
  `gpt-5.6-sol`.
- Cursor: the `agent` CLI installed and authenticated with access to
  `cursor-grok-4.5-high`.
- Python 3 on `PATH` for hook and MCP scripts.

## Known limitations

- Shell writes are advisory-only; reliably classifying arbitrary shell
  commands is outside this gate.
- Gating is per session, not per task.
- MCP advisors receive the structured payload and readable workspace, not the
  executor's entire transcript.
