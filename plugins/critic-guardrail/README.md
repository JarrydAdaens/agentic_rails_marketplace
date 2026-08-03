# critic-guardrail

Cross-vendor actor-critic guardrail for Claude Code. The executor must consult
an antagonistic, read-only critic at decision points, and the session's first
write is gated until that consult happens. Unlike `advisor-guardrail`, the
second opinion comes from *outside* the Claude model family: a bundled stdio
MCP tool, `consult_critic`, backed by `gpt-5.6-sol` at high reasoning through
the user's existing Codex CLI login. Same-family models share blind spots; the
critic exists to catch what Fable, Opus, Sonnet, and Haiku would all miss
together.

> **Codex users:** this plugin is Claude Code only — its point is reaching from
> Claude out to Codex. The Codex-side sibling, `advisor-codex-guardrail`,
> already consults `gpt-5.6-sol` natively.

## How it works

| Piece | Mechanism |
| --- | --- |
| Critic | `consult_critic(task, stage, approach, evidence, question)` MCP tool, model `gpt-5.6-sol`, high reasoning, read-only sandbox, adversarial persona |
| Write gate | `PreToolUse` on `Write`, `Edit`, `MultiEdit`, `NotebookEdit` — denied until one consult has occurred this session |
| Consult marker | `PostToolUse` on `consult_critic` — a completed consult unlocks writes for the session |
| Protocol | `SessionStart` injects the consult protocol into context; stale markers are cleaned |

The bundled MCP server runs `codex exec` ephemerally in the executor's
workspace with a read-only sandbox, so the critic can inspect repository files
but cannot modify them. It uses the installed CLI login; no API key is read or
required. Python's standard library and the `codex` executable must be on PATH.

On install, review and trust the hooks and the local MCP command. This trust
prompt is expected: the plugin executes bundled Python and, for a consultation,
starts the locally authenticated Codex CLI. Authentication, unavailable-model,
missing-executable, and timeout failures are returned as actionable tool
errors.

The first completed consultation creates a marker under
`<temp>/critic-guardrail-markers/` and unlocks writes for that session. A fresh
session remains locked.

## Choosing between advisor-guardrail and critic-guardrail

Both gate the session's first write behind a consult; install one, not both —
two gates mean two mandatory consults per session. `advisor-guardrail` gives a
same-ecosystem senior advisor (Opus) whose advice the executor is told to
weight heavily. `critic-guardrail` gives a cross-vendor antagonist whose
objections the executor is told to test against evidence, not obey. Prefer the
critic when the failure mode you fear is confident same-family groupthink;
prefer the advisor when you want a capability lift for a smaller executor.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so Bash and shell-command surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation.
- The critic sees the structured payload and the readable workspace, not the
  executor transcript. Thin evidence produces a thin critique.
- Requires the Codex CLI on PATH with an authenticated login, access to the
  fixed `gpt-5.6-sol` model, and consumes existing ChatGPT/Codex quota.
- An adversarial critic will sometimes object to sound approaches; the
  protocol tells the executor to test objections against evidence rather than
  capitulate, but a suggestible executor may still over-correct.
