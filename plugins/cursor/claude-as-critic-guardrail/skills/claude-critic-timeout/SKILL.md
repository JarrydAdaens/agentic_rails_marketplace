---
name: claude-critic-timeout
description: >-
  View or persist the Claude critic consult timeout for this project. Use when
  the user asks how long critic consults may run, wants to change that limit,
  restore its default, or cancel a pending change.
argument-hint: "[seconds|default|cancel]"
disable-model-invocation: true
---

# Claude critic consult timeout

Resolve the installed plugin root and project workspace, then invoke the CLI.

With no user value, explain the timeout and wait for the user's next answer;
do not change the setting:

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_timeout.py --seconds --workspace <PROJECT_ROOT>
```

With a user value, run:

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_timeout.py --seconds <USER_VALUE> --workspace <PROJECT_ROOT>
```

Accept positive digits such as `123`, spelled values such as `fourhundred`, or
`default` to restore 600 seconds. `cancel`, `nevermind`, `abort`, and similar
back-out wording must leave the config unchanged. Copy the CLI output verbatim.

The setting is `consult_timeout_seconds` in the project JSONC config. The CLI
also shows its full path and points out advanced manually editable values,
including `health_timeout_seconds`.
