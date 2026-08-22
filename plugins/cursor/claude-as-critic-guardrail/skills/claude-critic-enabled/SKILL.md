---
name: claude-critic-enabled
description: >-
  Enable or disable the Claude critic guardrail for this project and persist
  the choice in its harness JSONC config. Use when the user says to enable,
  disable, engage, disengage, turn on, or turn off the critic.
argument-hint: "<enabled|disabled>"
disable-model-invocation: true
---

# Claude critic enabled

Resolve the installed plugin root and project workspace, then pass the user's
intent to the CLI. Accept ordinary boolean language: `true`, `false`, `yes`,
`no`, `enabled`, `disabled`, `enable`, `disable`, `on`, `off`, `engage`, or
`disengage`.

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_enabled.py --enabled <USER_INTENT> --workspace <PROJECT_ROOT>
```

Copy stdout verbatim. On success it emits exactly whether the critic is now
Enabled (and will criticize the agent) or Disabled (and will not do anything).
The hook remains registered, but a disabled critic performs no health probe,
injects no protocol, and allows writes immediately.
