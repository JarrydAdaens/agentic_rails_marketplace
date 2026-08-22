# cursor-as-critic-guardrail

Cross-vendor actor-critic guardrail for Claude Code and Codex. The executor must consult
an antagonistic, read-only critic at decision points, and the session's first
write is gated until that consult happens. The critic runs through the user's
authenticated Cursor Agent CLI (`agent`) in read-only ask mode.

The critic attacks the work to improve it, not to halt it. Every material
objection carries a recommended correction and a statement of whether work can
continue meanwhile; hypotheses are labeled and paired with the test that would
confirm them; and a proposal to stop is attacked as hard as the code, requiring
the strongest case for continuing, why it fails, and why stopping is justified.

Claude Code and Codex can use this plugin to reach out to Cursor. Cursor itself
is not a consumer because that would not provide a cross-vendor perspective.

## How it works

| Piece | Mechanism |
| --- | --- |
| Critic | `consult_critic(task, stage, approach, evidence, question, model?)` MCP tool, Cursor Agent ask mode, adversarial persona |
| Model default | Built-in first-run default `cursor-grok-4.6-high` (high reasoning, standard speed); successful calls remember the chosen model at project level |
| Write gate | `PreToolUse` on `Write`, `Edit`, `MultiEdit`, `NotebookEdit` — denied until one consult has occurred this session |
| Consult marker | `PostToolUse` on `consult_critic` — a completed consult unlocks writes for the session |
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

The Cursor Agent CLI must be installed and authenticated. On Cursor-hosted
Windows adapters, the plugin restores the registry-backed user and machine
PATH, recognizes WinGet's UV shim, and resolves an absolute `agent.cmd` before
launch. `AGENTIC_RAILS_UV` is optional; the launcher never falls back to the
global Python environment. Other hosts require Python 3. The plugin uses
Cursor's existing login and does not read an API key.

## Per-project model memory

The optional `model` argument selects the model for the current consultation.
After a successful call, that model becomes the default for this project only:

```text
harness/cursor-as-critic-guardrail/cursor-config.json
```

```json
{
  "default_model": "cursor-grok-4.6-high"
}
```

Calls that omit `model` reuse this file. If the file does not exist, the plugin
uses `cursor-grok-4.6-high` and creates the file after the first successful consult.
Changing one project's default never changes another project. A failed model
selection is not persisted, so an unavailable model cannot poison a working
default. The file may also be edited directly; use an exact model ID reported
by `agent models`.

Examples available on the development machine at authoring time included
`composer-2.5`, `claude-fable-5-thinking-high`, and
`cursor-grok-4.5-low`. Available IDs are account- and version-dependent.

## Consult timeout

The default cap is 600 seconds. Raise it for very large repositories:

```jsonc
// .claude/settings.json
{ "env": { "CURSOR_CRITIC_TIMEOUT_SECONDS": "900" } }
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
`<temp>/cursor-as-critic-guardrail-markers/` and unlocks writes for that
session. A fresh session remains locked.

Install only one first-write consultation guardrail at a time. Installing this
beside `local-advisor-guardrail` or `codex-as-critic-guardrail` creates independent
gates and therefore requires multiple consultations.

## Known limitations

- Shell commands are advisory-only. Reliably parsing shell writes is too
  fragile, so shell surfaces are intentionally ungated.
- Gating is per session, not per task; a long multi-task session forces only
  its first consultation.
- The critic sees the structured payload and readable workspace, not the
  executor transcript. Thin evidence produces a thin critique.
- Model IDs can change with Cursor accounts and releases; run `agent models`
  and choose an exact available ID.
- A consultation blocks the MCP server until it completes; the server handles
  one consult at a time.
- The project config is written only after a successful consultation. Until
  then, a missing config seam silently falls back to `cursor-grok-4.6-high`.
