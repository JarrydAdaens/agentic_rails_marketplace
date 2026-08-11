# advisor-codex-guardrail

Actor-critic guardrail for Codex. The executor must consult a stronger,
read-only advisor at decision points, and the session's first `apply_patch` is
gated until that consult happens. The advisor is a bundled stdio MCP tool,
`consult_advisor`, backed by `gpt-5.6-sol` at high reasoning through the user's
existing Codex login.

The advisor is tenacious by design. A blocker is treated as a routing decision
rather than an ending condition: every concern arrives with a forward path, a
repeated approach gets called out, and recommending that the executor stop
requires a concrete justification — stop reason, evidence, the case for
continuing, alternatives tried and untried, and why no other work can proceed.

> **Claude Code users:** this plugin is Codex only. The Claude equivalent — an
> Opus advisor subagent — ships as a separate plugin, `advisor-guardrail`, so
> neither tool ever loads the other's payload.

## How it works

| Piece | Mechanism |
| --- | --- |
| Advisor | `consult_advisor(task, stage, approach, evidence, question)` MCP tool, model `gpt-5.6-sol`, high reasoning, read-only sandbox |
| Write gate | `PreToolUse` on `apply_patch` — denied until one consult has occurred this session |
| Consult marker | `PostToolUse` on `consult_advisor` — a completed consult unlocks writes for the session |
| Protocol | `SessionStart` injects the consult protocol into context; stale markers are cleaned |

The bundled MCP server runs `codex exec` ephemerally in the executor's
workspace with a read-only sandbox, so the advisor can inspect repository files
but cannot modify them. It uses the installed CLI login; no API key is read or
required. Python's standard library and the `codex` executable must be on PATH.

On install, review and trust the hooks and the local MCP command. This trust
prompt is expected: the plugin executes bundled Python and, for a consultation,
starts the locally authenticated Codex CLI. Authentication, unavailable-model,
missing-executable, and timeout failures are returned as actionable tool
errors.

The first completed consultation creates a marker under
`<temp>/advisor-codex-guardrail-markers/` and unlocks writes for that session. A
fresh session remains locked.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so shell-command surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation.
- The advisor sees the structured payload and the readable workspace, not the
  executor transcript. Thin evidence produces poor advice.
- Requires access to the fixed `gpt-5.6-sol` model and consumes existing
  ChatGPT/Codex quota.
