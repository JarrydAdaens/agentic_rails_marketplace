# codex-as-critic-guardrail

Cross-vendor actor-critic guardrail for Claude Code and Cursor. The executor must consult
an antagonistic, read-only critic at decision points, and the session's first
write is gated until that consult happens. Unlike `local-advisor-guardrail`, the
second opinion comes from *outside* the Claude model family: a bundled stdio
MCP tool, `consult_critic`, backed by `gpt-5.6-sol` at high reasoning through
the user's existing Codex CLI login. Same-family models share blind spots; the
critic exists to catch what Fable, Opus, Sonnet, and Haiku would all miss
together.

The critic attacks the work to improve it, not to halt it. Every material
objection carries a recommended correction and a statement of whether work can
continue meanwhile; hypotheses are labeled and paired with the test that would
confirm them; and a proposal to stop is attacked as hard as the code, requiring
the strongest case for continuing, why it fails, and why stopping is justified.

Codex users who want a constructive checkpoint use the unified
`local-advisor-guardrail`, which consults `gpt-5.6-sol` locally.

> Formerly published as `critic-guardrail`. Existing installs migrate
> automatically through the marketplace `renames` map.

## How it works

| Piece | Mechanism |
| --- | --- |
| Critic | `consult_critic(task, stage, approach, evidence, question)` MCP tool, model `gpt-5.6-sol`, high reasoning, read-only sandbox, adversarial persona |
| Write gate | Claude `PreToolUse`; Cursor `preToolUse` on `Write`, `StrReplace`, `Delete`, and compatible edit names — denied until one consult has occurred this session |
| Consult marker | Claude `PostToolUse`; Cursor `afterMCPExecution` on `consult_critic` — a completed consult unlocks writes for the session |
| Protocol | `SessionStart` injects the consult protocol into context; stale markers are cleaned |

The bundled MCP server runs `codex exec` ephemerally in the executor's
workspace with a read-only sandbox, so the critic can inspect repository files
but cannot modify them. It uses the installed CLI login; no API key is read or
required. The `codex` executable must be on `PATH`. Claude Code requires Python
3; Cursor runs the bundled server and hooks through `uv` without invoking the
global Python environment directly.

On install, review and trust the hooks and the local MCP command. This trust
prompt is expected: the plugin executes bundled Python and, for a consultation,
starts the locally authenticated Codex CLI. Authentication, unavailable-model,
missing-executable, and timeout failures are returned as actionable tool
errors. On Cursor, an absolute native `cmd.exe` starts a bundled UV-only
launcher, while MCP paths use `${PLUGIN_ROOT}` and an explicit plugin-root
working directory. The launcher accepts `AGENTIC_RAILS_UV`, checks standard UV
install locations, and fails clearly when UV is unavailable; it has no direct
Python fallback.

### Cursor installation

Registering the marketplace or writing `enabled: true` into
`.cursor/settings.json` does not install this plugin. Install
`codex-as-critic-guardrail` through Cursor's interactive `/plugin` Marketplace
screen or **Customize → Marketplace**, choose project or user scope, approve the
MCP server, and open a fresh session. The expected MCP tool is
`plugin-codex-as-critic-guardrail-codex-as-critic-guardrail:consult_critic`.

The Cursor gate is deliberately fail-open. It activates only after the live MCP
server has completed tool registration. If the server, launcher, or hook input
is unavailable, writes proceed with an actionable diagnostic rather than an
empty fail-closed denial.

The first completed consultation creates a marker under
`<temp>/codex-as-critic-guardrail-markers/` and unlocks writes for that session.
A fresh session remains locked.

## Consult timeout

A consultation is a full Codex run at high reasoning, and it gets slower the
larger and less familiar the repository is. Measured across real sessions, the
median consult took 51 seconds, the 90th percentile 132 seconds, and the longest
success 178 seconds.

The default cap is therefore **600 seconds**. Claude Code imposes no competing
limit — a stdio MCP server has no per-request timer, and an unset
`MCP_TOOL_TIMEOUT` defaults to roughly 28 hours — so this cap is the only one
that applies. Raise it for very large repositories:

```jsonc
// .claude/settings.json
{ "env": { "CODEX_CRITIC_TIMEOUT_SECONDS": "900" } }
```

A timeout error reports the limit, names the variable, and includes whatever
Codex managed to emit before it was cut off.

## Choosing between local-advisor-guardrail and codex-as-critic-guardrail

Both gate the session's first write behind a consult. Installing both is
supported and intentionally requires both consultations before the first
write; each successful consult unlocks only its own gate. Install one when one
independent review is enough. `local-advisor-guardrail` gives a
same-ecosystem senior advisor (Opus) whose advice the executor is told to
weight heavily. `codex-as-critic-guardrail` gives a cross-vendor antagonist
whose objections the executor is told to test against evidence, not obey. Prefer
the critic when the failure mode you fear is confident same-family groupthink;
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
- A consultation blocks the MCP server until it completes; the server handles
  one consult at a time, which is all the write gate ever asks of it.
- An adversarial critic will sometimes object to sound approaches; the
  protocol tells the executor to test objections against evidence rather than
  capitulate, but a suggestible executor may still over-correct.
