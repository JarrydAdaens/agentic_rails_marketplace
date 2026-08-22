---
name: claude-advisor-model
description: >-
  Select and persist the Claude advisor model and reasoning effort for this
  project. Use when the user wants a different advisor model or effort level.
argument-hint: "[model and/or effort, e.g. opus high or 2a]"
disable-model-invocation: true
---

# Claude advisor model

Run the model selector from the installed plugin root against the project
workspace:

```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_model.py --model "<USER_SELECTION>" --workspace <PROJECT_ROOT>
```

If the user supplies no selection, omit the value after `--model`; the CLI
prints the Claude-style model menu plus the effort table. It accepts the model
aliases `haiku`, `sonnet`, `opus`, and `fable`; a specific or future model id
such as `opus-4.7` or `deity`; effort names; model/effort phrases like
`opus high`; and compact choices such as `2b` or `4f`. The menu shows
`(Current)` beside the selected listed model and effort; `cancel`, `0`, or `a`
leaves the saved settings unchanged.

Copy the successful confirmation verbatim. The choice is validated and saved
as the project default for new advisor sessions.
