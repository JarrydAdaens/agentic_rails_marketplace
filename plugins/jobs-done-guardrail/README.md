# jobs-done-guardrail

Deterministic "you don't get to leave broken" guardrail, delivered as a
marketplace plugin. A Stop hook treats the end of an agent turn with relevant
uncommitted code changes as a "jobs done" claim, then requires the project's
build and unit-test commands to pass before the agent may hand control back to
the human. It spends no LLM judgment: pass/fail is the exit code of the
project's own build and test commands, and a SHA-256 fingerprint of the dirty
worktree skips re-validation of states that already passed.

Supports Claude Code and Cursor. Claude blocks Stop by exit status; Cursor uses
its native `followup_message` response to continue the repair loop. The plugin
remains absent from the Codex catalog because Codex Stop-hook packaging has not
been adopted here.

## What the plugin registers

One Stop hook (`hooks/stop-jobs-done-guardrail.ps1`, PowerShell, 600s
timeout). On failure it exits 2 with a focused repair prompt — failed stage,
command, exit code, trimmed relevant output, full log path, and strict
fix-only-this instructions — emitted to both stdout and stderr. After
`maxRepairAttempts` failures in one turn it stops repairing and demands human
review. On install, Claude Code asks you to review and trust the hook.

## Adopting it in a project (the seam)

The plugin is inert in any project until the seam exists. Create
`harness/jobs-done-guardrail/` in the target project:

1. Copy `examples/config.example.json` to
   `harness/jobs-done-guardrail/config.json` and set the project's build and
   test commands, plus the file-extension and path filters that define a
   "relevant" change.
2. Optionally copy `examples/eval-mode.example.json` to
   `harness/jobs-done-guardrail/eval-mode.json` to control the mode
   (`enabled` | `force` | `ask` | `plan` | `disabled`). Missing file means
   `enabled`. The `AGENTIC_RAILS_EVAL_MODE` environment variable overrides it.
3. Add to the project's `.gitignore`:

   ```gitignore
   # jobs-done-guardrail runtime output
   harness/jobs-done-guardrail/runs/
   harness/jobs-done-guardrail/state/
   ```

No seam config (or `"enabled": false`) means the hook exits silently, so the
plugin is safe to install system-wide and adopt per project.

## Trigger rules

Runs only when all are true: a Stop hook fired; permission mode is not `plan`;
mode is `enabled` or `force`; at least one relevant uncommitted non-markdown
file changed; and the worktree fingerprint differs from the last passing one
(unless mode is `force`). Everything else — markdown-only changes, clean
worktrees, already-passed fingerprints, non-git folders — exits 0 without
running anything.

## Behavior on failure

Build runs first; test only runs when build passes (fail-fast). After a
repair, the next Stop reruns the whole sequence from build. Runtime evidence
lands in `harness/jobs-done-guardrail/runs/<timestamp>/` (changed files,
fingerprint, stage outputs, `result.json`, repair prompt) and passing
fingerprints in `state/` — both git-ignored, durable across turns.

## Known limitations (accepted trade-offs)

- **Per-turn claim, not goal completion**: the gate enforces "the agent is not
  handing back broken build/tests", not "the human's goal is met".
- Filters are extension/path based; an exotic change type outside
  `includeExtensions` will not trigger the gate.
- Windows-first: the hook command invokes `powershell`; the script is
  PowerShell 5+/7 compatible but untested off Windows.

## Provenance

Promoted from the `rails-eval-jobs-done` verifier in the Quota-Tank project
(itself an evolution of fishing-line's `jobs-done-gate`), via the tooling
repo's proposals inbox on 2026-07-10. Renamed to drop the `rails-` prefix and
the "eval" vocabulary per the marketplace naming convention. Changes from the
origin: seam moved from `verifiers/rails-eval-jobs-done/` to
`harness/jobs-done-guardrail/`, hook registration became native plugin
`hooks.json` instead of hand-merged `.claude/settings.json`/`.codex/hooks.json`,
non-git folders and malformed hook payloads now fail open instead of blocking,
and the repair prompt is emitted to stderr as well as stdout so Claude's Stop
hook acts on it.
