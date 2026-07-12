# advisor-guardrail

Actor-critic guardrail for Claude Code and Codex. An executor must consult a
stronger, read-only advisor at decision points, with the first supported write
surface gated per session. Claude keeps its Fable subagent; Codex gains the
`consult_advisor` MCP tool backed by `gpt-5.6-sol` at high reasoning through the
user's existing Codex login.

## Platform implementations

| Platform | Advisor invocation | Model | Gated writes |
| --- | --- | --- | --- |
| Claude Code | Task/Agent `advisor-guardrail:advisor` | Fable | Write, Edit, MultiEdit, NotebookEdit |
| Codex | `consult_advisor(task, stage, approach, evidence, question)` | `gpt-5.6-sol`, high reasoning | `apply_patch` |

Claude's agent, timing, structured payload, and 120-word contract are unchanged.
Codex's bundled stdio MCP server runs `codex exec` ephemerally in the executor's
workspace with a read-only sandbox, so it can inspect repository files but
cannot modify them. It uses the installed CLI login; no API key is read or
required. Python's standard library and the `codex` executable must be on PATH.

On install, review and trust the hooks and local MCP command. This trust prompt
is expected: the plugin executes bundled Python and, for a Codex consultation,
starts the locally authenticated Codex CLI. Authentication, unavailable-model,
missing-executable, and timeout failures are returned as actionable tool errors.

The first completed consultation creates a neutral marker under
`<temp>/advisor-guardrail-markers/` and unlocks writes for that session. Legacy
`<temp>/claude-advisor-markers/` markers are recognized during migration. A
fresh session remains locked.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so Bash and shell-command surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation.
- Advisors see the structured payload and readable workspace, not the executor
  transcript. Thin evidence produces poor advice.
- Claude still depends on the `fable` alias being available. Codex requires
  access to the fixed `gpt-5.6-sol` model and consumes existing ChatGPT/Codex
  quota.
