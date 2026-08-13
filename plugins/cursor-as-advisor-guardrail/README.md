# cursor-as-advisor-guardrail

Cross-vendor advisor guardrail for Claude Code and Codex. The executor must consult a
helpful, read-only advisor at decision points, and the session's first write is
gated until that consult happens. The advisor runs through the user's
authenticated Cursor Agent CLI (`agent`) in read-only ask mode.

The intended pairing is a Claude Code or Codex executor supported by an
independent Cursor model. The advisor is constructive rather than antagonistic: it returns
a plan, course correction, or completion verdict and concentrates on decisions,
risks, and the next useful check.

It is also tenacious. A blocker is treated as a routing decision rather than an
ending condition: every concern arrives with a forward path, a repeated approach
gets called out, and recommending that the executor stop requires a concrete
justification — stop reason, evidence, the case for continuing, alternatives
tried and untried, and why no other work can proceed.

Claude Code and Codex can use this plugin to reach out to Cursor. Cursor itself
is not a consumer; use `local-advisor-guardrail` for a Cursor child advisor.

## How it works

| Piece | Mechanism |
| --- | --- |
| Advisor | `consult_advisor(task, stage, approach, evidence, question, model?)` MCP tool, Cursor Agent ask mode, constructive persona |
| Model default | Built-in first-run default `cursor-grok-4.6-high` (high reasoning, standard speed); successful calls remember the chosen model at project level |
| Write gate | `PreToolUse` on `Write`, `Edit`, `MultiEdit`, `NotebookEdit` — denied until one consult has occurred this session |
| Consult marker | `PostToolUse` on `consult_advisor` — a completed consult unlocks writes for the session |
| Protocol | `SessionStart` injects the consult protocol into context; stale markers are cleaned |

The bundled MCP server launches `agent --print --mode ask` in the executor's
workspace. Cursor documents ask mode as read-only; the command never passes
`--force`, `--yolo`, `--auto-review`, or automatic MCP approval. It does pass
`--trust` because non-interactive Cursor rejects newly seen workspaces without
that acknowledgement; `--trust` accepts workspace contents but does not
override read-only ask mode. The prompt travels over UTF-8 stdin rather than
the Windows command line. On Windows, Cursor's OS sandbox is unavailable, so
the command explicitly disables that unsupported layer while retaining
read-only ask mode.

Python's standard library and the `agent` executable must be on `PATH`. The
plugin uses Cursor's existing login and does not read an API key.

## Per-project model memory

The optional `model` argument selects the Cursor model for the current
consultation. After a successful call, that model becomes the default for this
project only:

```text
harness/cursor-as-advisor-guardrail/config.json
```

```json
{
  "default_model": "cursor-grok-4.6-high"
}
```

Calls that omit `model` reuse this file. If the file does not exist, the plugin
uses `cursor-grok-4.6-high` and creates the file after the first successful
consult.
Changing one project's default never changes another project. A failed model
selection is not persisted. The file may also be edited directly; use an exact
model ID reported by `agent models`.

Available IDs are account- and version-dependent. The independent value comes
from the Cursor execution stack and selected model, so choose a model that
meaningfully complements the Claude Opus executor.

`docs/setting-the-advisor-model.md` is the deep reference for choosing and
verifying a model, including the reasoning-effort and Fast variants and the
traps around inexact IDs. `docs/cursor-model-ids.md` is the companion catalog
that maps informal names ("the latest Grok") to exact IDs. Both are written to
be handed to an agent as standalone documents.

## Consult timeout

The default cap is 600 seconds. Raise it for very large repositories:

```jsonc
// .claude/settings.json
{ "env": { "CURSOR_ADVISOR_TIMEOUT_SECONDS": "900" } }
```

A timeout reports the limit, names the variable, and includes whatever Cursor
managed to emit before it was stopped.

## Installation and trust

Install through the Agentic Rails marketplace for Claude Code or Codex. Review
and trust the hooks and local MCP command when prompted. In Codex, use `/hooks`
to trust the bundled lifecycle hooks and enable the plugin MCP server before
starting a fresh thread. Authentication, unavailable-model, missing-executable,
malformed-config, and timeout failures return actionable tool errors.

The first completed consultation creates a marker under
`<temp>/cursor-as-advisor-guardrail-markers/` and unlocks writes for that
session. A fresh session remains locked.

Install only one first-write consultation guardrail at a time unless multiple
independent consultations are intentional. Installing this beside
`local-advisor-guardrail`, `cursor-as-critic-guardrail`, or
`codex-as-critic-guardrail` creates independent gates.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so shell surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation. The injected protocol still asks for planning,
  pivot, stuck, and completion consultations throughout the work.
- The advisor sees the structured payload and readable workspace, not the
  executor transcript. Thin evidence produces thin advice.
- Model IDs can change with Cursor accounts and releases; run `agent models`
  and choose an exact available ID.
- A consultation blocks the MCP server until it completes; the server handles
  one consult at a time.
- The project config is written only after a successful consultation. Until
  then, a missing config seam silently falls back to `cursor-grok-4.6-high`.
