---
name: wpf-visual-quality-gate
description: >-
  Independent evaluator gate for WPF changes that affect visible UI: build,
  tests, live launch, screenshots before and after a real UI interaction, and
  a pass/fail report against explicit packet criteria.
metadata:
  version: "1.1"
---

# WPF Visual Quality Gate

Use this evaluation for any WPF change that affects visible UI, navigation,
state presentation, layout, or user interaction. Visible UI work is not done
until the running app has been launched, driven through the changed
interaction with real input, and screenshot-verified against explicit pass
criteria.

## Runner

Use an independent evaluator sub-agent when available. The evaluator must not
edit files. It validates only the packet criteria and reports failures.

Preferred runner order:

1. `quality-gate-persona` — dispatch as a sub-agent with the evaluator packet
   as its prompt (in Claude Code, via the Agent tool).
2. `wpf-persona` — when the evaluation needs deeper WPF or XAML judgment.
3. An equivalent independent evaluator agent in another agentic IDE.
4. Human evaluator — when sub-agents or desktop screenshots are unavailable;
   hand over the human checklist.

The `wpf-tree-sensor` skill may be used for supporting UI Automation tree
evidence (control presence, automation IDs, enabled/offscreen state). It
supplements screenshot inspection; it never replaces it.

## Project Defaults

Each adopting project provides these in
`harness/wpf-visual-quality-gate/defaults.md` (created at adoption; see the
plugin skill). They are the per-project seam; this gate document stays as
shipped. A story's packet may override them when it needs a different launch
path.

| Field | Value |
| --- | --- |
| Visual launch command | `<path\to\YourApp.exe --your-flags>` |
| Window title | `<main window title>` |
| Cleanup command | `<command that stops the app process>` |

## Evaluator Packet

The main agent must provide:

- Task goal
- Expected visible behavior
- Visual launch command (project default unless overridden)
- Window title (project default unless overridden)
- Interaction path
- Pass criteria
- Cleanup command (project default unless overridden)
- Commands already run
- Files changed

## Gate Steps

1. Confirm the relevant WPF build passed.
2. Confirm relevant tests passed.
3. Launch the app through the visible evaluation path.
4. Capture a screenshot of the initial state.
5. Perform the required interaction through real UI input.
6. Capture a screenshot of the target state.
7. Compare screenshots against the packet pass criteria.
8. Clean up the running WPF process.

## Pass Criteria

- App launches into the expected visible screen.
- Changed controls are visible and discoverable.
- Required interaction works through real UI input.
- Target state is visible after interaction.
- No obvious clipping, overlap, invisible controls, or misleading status is
  present.
- Cleanup leaves no running app process that locks build outputs.

## Attempt Loop

- Evaluation 1 fails: main agent fixes only evaluator-listed failures.
- Evaluation 2 fails: stop and escalate to a human.
- Blocked evaluation: stop and provide the human checklist.

## Report Format

The evaluator returns exactly these sections:

```text
PASS or FAIL

Observed
- <what was actually seen>

Failures
- <specific failed criterion, or None>

Screenshots inspected
- <initial state>
- <target state>

Commands run
- <command and result>

Human checklist
- <only include when failed twice or blocked>
```

## Human Checklist

Give the human:

- Original task goal
- Expected visible behavior
- Visual launch command
- Window title
- Interaction path
- Pass criteria
- Evaluator failures
- Commands run
- Files changed
