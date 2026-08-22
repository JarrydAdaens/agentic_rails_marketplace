---
name: claude-critic-init
description: >-
  Create the project harness config for claude-as-critic-guardrail
  (harness/claude-as-critic-guardrail/config.json) with commented defaults for
  model, effort, and timeouts. Use when setting up the critic in a new project
  or when the user asks to init/write the critic config.
disable-model-invocation: true
---

# Claude critic config init

Write the default harness config to disk and show the user its absolute path.
Do not invent a different schema.

## Steps

1. Resolve the plugin root for `claude-as-critic-guardrail`.
2. Run from that root against the **project workspace** (not the plugin cache):

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_init.py --workspace <PROJECT_ROOT>
```

If the file already exists and the user wants a fresh defaults file:

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_init.py --workspace <PROJECT_ROOT> --force
```

3. Show the CLI stdout to the user **verbatim**, especially the `Path:` line.
4. Remind them the file is JSONC (`//` comments are valid), and which fields to
   edit: `enabled`, `model`, `effort`, `consult_timeout_seconds`, `health_timeout_seconds`.
   `effort` must be one of `low`, `medium`, `high`, `xhigh`, `max`; `model`
   takes a Claude alias (`opus`, `sonnet`, `fable`) or a full model id.
5. After they edit, suggest `/claude-critic-health` or a new session so health
   reloads the config.
