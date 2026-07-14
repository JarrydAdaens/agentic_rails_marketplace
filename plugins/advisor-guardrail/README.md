# advisor-guardrail

Actor-critic guardrail for Claude Code. An executor must consult a stronger,
read-only advisor subagent at decision points, and the session's first write is
gated until that consult happens. The advisor runs on Opus.

> **Codex users:** this plugin is Claude Code only. The Codex equivalent — a
> `consult_advisor` MCP tool backed by `gpt-5.6-sol` — ships as a separate
> plugin, `advisor-codex-guardrail`, so neither tool ever loads the other's
> payload.

## How it works

| Piece | Mechanism |
| --- | --- |
| Advisor | Task/Agent subagent `advisor-guardrail:advisor`, model Opus, read-only (`Read`, `Grep`, `Glob`) |
| Write gate | `PreToolUse` on `Write`, `Edit`, `MultiEdit`, `NotebookEdit` — denied until one consult has occurred this session |
| Consult marker | `PostToolUse` on `Task`/`Agent` — an advisor consult unlocks writes for the session |
| Protocol | `SessionStart` injects the consult protocol into context; stale markers are cleaned |

On install, review and trust the hooks. This trust prompt is expected: the
plugin executes bundled Python at tool-use and session-start time. Only the
standard library is used; no network access and no API key.

The first completed consultation creates a neutral marker under
`<temp>/advisor-guardrail-markers/` and unlocks writes for that session. Legacy
`<temp>/claude-advisor-markers/` markers are recognized during migration. A
fresh session remains locked.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so Bash and shell-command surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation.
- The advisor sees the structured payload and the readable workspace, not the
  executor transcript. Thin evidence produces poor advice.
- The advisor runs on Opus. The capability lift is greatest with a Sonnet
  executor; an Opus executor gets a same-tier second opinion rather than a
  stronger one.
