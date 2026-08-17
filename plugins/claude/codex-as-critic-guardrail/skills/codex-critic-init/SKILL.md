---
name: codex-critic-init
description: >-
  Create the project harness config for codex-as-critic-guardrail
  (harness/codex-as-critic-guardrail/config.json) with commented defaults for
  model, effort, fast, and timeouts. Use when setting up the critic in a new
  project or when the user asks to init/write the critic config.
disable-model-invocation: true
---

# Codex critic config init

Write the default harness config to disk and show the user its absolute path.
Do not invent a different schema.

## Steps

1. Resolve the plugin root for `codex-as-critic-guardrail`.
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
   edit: `model`, `effort`, `fast`, `consult_timeout_seconds`,
   `health_timeout_seconds`.
5. After they edit, suggest `/codex-critic-health` or a new session so health
   reloads the config.
