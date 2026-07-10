---
name: wpf-visual-quality-gate
description: >-
  Use this skill for any WPF change that affects visible UI, navigation,
  state presentation, layout, or user interaction — before declaring the work
  done. It dispatches an independent evaluator that launches the app,
  screenshots the initial state, performs the target interaction through real
  input, screenshots the result, and reports pass/fail against explicit
  criteria. Also use it to adopt the gate in a WPF project or to write an
  evaluator packet.
metadata:
  version: "1.1"
---

# WPF Visual Quality Gate

Closes the gap between "it compiles and the tests pass" and "the change is
actually visible and works in the running app." Build and test success can
miss clipping, overlap, invisible controls, misleading status, and
interactions that only fail on the live desktop. The gate gives visible UI
work a concrete stop condition, with an independent evaluator — not the
implementing agent — delivering the verdict.

The full procedure, runner order, pass criteria, attempt loop, and report
format are in `references/wpf-visual-quality-gate.md`. That document stays in
the plugin and is updated through the marketplace; never copy it into a
project.

## Adopting the gate in a project (once)

1. Create `context/evaluations/wpf-visual-quality-gate-defaults.md` in the
   target project containing the filled Project Defaults table from the gate
   document: visual launch command, window title, cleanup command. This file
   is the entire per-project seam.
2. Wire the trigger into the project's `AGENTS.md` (or `CLAUDE.md`) so the
   gate is mandatory rather than advisory:

   > - For any change affecting visible WPF UI, run the
   >   `wpf-visual-quality-gate` skill before declaring the work done, using
   >   an independent evaluator sub-agent when available.

## Running the gate (per UI story)

1. Write an evaluator packet — task goal, expected visible behavior, launch
   command, window title, interaction path, pass criteria, cleanup command,
   commands already run, files changed. Take launch/title/cleanup from the
   project defaults file unless the story needs an override. A filled example
   is in `references/packet-example.md`.
2. Dispatch the evaluator with the packet as its prompt, following the runner
   order in the gate document (`quality-gate-persona`, then `wpf-persona`,
   then an equivalent independent evaluator, then a human with the checklist).
3. Act on the report: fix only evaluator-listed failures, re-run once, and
   escalate to a human after a second failure or a blocked evaluation.

## Requirements

- Windows desktop session able to launch and display the target WPF app.
- Screenshot capture in the active agentic IDE or evaluator environment.
- Real UI input capability — IDE-driven input, UI Automation, or manual
  evaluator steps.
- The gate degrades to a human checklist when no evaluator sub-agent is
  available.
