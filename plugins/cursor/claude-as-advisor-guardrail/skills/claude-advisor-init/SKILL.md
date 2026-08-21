---
name: claude-advisor-init
description: >-
  Create the project harness config for claude-as-advisor-guardrail
  (harness/claude-as-advisor-guardrail/config.json) with commented defaults for
  model, effort, and timeouts. Use when setting up the advisor in a new project
  or when the user asks to init/write the advisor config.
disable-model-invocation: true
---

# Claude advisor config init

Write the default harness config to disk and show the user its absolute path.
Do not invent a different schema.

## Steps

1. Resolve the plugin root for `claude-as-advisor-guardrail`.
2. Run from that root against the **project workspace** (not the plugin cache):

```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_init.py --workspace <PROJECT_ROOT>
```

If the file already exists and the user wants a fresh defaults file:

```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_init.py --workspace <PROJECT_ROOT> --force
```

3. Show the CLI stdout to the user **verbatim**, especially the `Path:` line.
4. Remind them the file is JSONC (`//` comments are valid), and which fields to
   edit: `model`, `effort`, `consult_timeout_seconds`, `health_timeout_seconds`.
   `effort` must be one of `low`, `medium`, `high`, `xhigh`, `max`; `model`
   takes a Claude alias (`opus`, `sonnet`, `fable`) or a full model id.
5. After they edit, suggest `/claude-advisor-health` or a new session so health
   reloads the config.
