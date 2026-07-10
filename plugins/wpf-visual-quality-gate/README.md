# wpf-visual-quality-gate

Evaluator-run visual quality gate for WPF desktop apps, delivered as a
marketplace plugin. For any change that affects visible UI, an independent
evaluator sub-agent launches the app, screenshots the initial state, performs
the target interaction through real input, screenshots the result, and
reports pass/fail against explicit criteria — so agents cannot declare
visible UI work done on build and unit tests alone.

Unlike `game-golden-screenshot-verifier`, the runner is not a script: it is an
evaluator sub-agent following a fixed procedure and report format. The payload
is one skill, `wpf-visual-quality-gate`, whose `references/` carry the gate
document (procedure, runner order, pass criteria, attempt loop, report format)
and a filled packet example. Works in both Claude Code and Codex (skills only,
no hooks); the preferred evaluator personas (`quality-gate-persona`,
`wpf-persona`) deploy from `agentic_rails_tooling`, with fallbacks for other
IDEs and for a human evaluator.

## Division of ownership

| Lives in the plugin (updated via marketplace) | Lives in the target project (the seam) |
| --- | --- |
| The gate document — procedure, criteria, report format | `context/evaluations/wpf-visual-quality-gate-defaults.md` — launch command, window title, cleanup command |
| The packet example | The trigger lines in the project's `AGENTS.md`/`CLAUDE.md` |

Per UI story, the implementing agent writes an evaluator packet and dispatches
the evaluator; the skill documents both steps.

## Requirements

- Windows desktop session able to launch and display the target WPF app.
- Screenshot capture and real UI input in the evaluator environment.
- An independent evaluator sub-agent when available; degrades to a human
  checklist otherwise.

## Provenance

Generalized from the Quota-Tank project's local gate (2026-07-09), previously
maintained as a drop-in verifier in `agentic_rails_tooling` and extracted here
as a plugin (v1.1: the gate document now stays in the plugin; only the
Project Defaults file is created in the target project).
