---
name: claude-advisor-enabled
description: >-
  Enable or disable the Claude advisor guardrail for this project and persist
  the choice in its harness JSONC config. Use when the user says to enable,
  disable, engage, disengage, turn on, or turn off the advisor.
argument-hint: "<enabled|disabled>"
disable-model-invocation: true
---

# Claude advisor enabled

Resolve the installed plugin root and project workspace, then pass the user's
intent to the CLI. Accept ordinary boolean language: `true`, `false`, `yes`,
`no`, `enabled`, `disabled`, `enable`, `disable`, `on`, `off`, `engage`, or
`disengage`.

```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_enabled.py --enabled <USER_INTENT> --workspace <PROJECT_ROOT>
```

Copy stdout verbatim. On success it emits exactly whether the advisor is now
Enabled (and will advise the agent) or Disabled (and will not do anything).
The hook remains registered, but a disabled advisor performs no health probe,
injects no protocol, and allows writes immediately.
