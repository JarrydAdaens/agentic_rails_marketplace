---
name: codex-advisor-init
description: >-
  Create the project harness config for codex-as-advisor-guardrail
  (harness/codex-as-advisor-guardrail/config.json) with commented defaults for
  enabled state, model, effort, fast, and timeouts. Use when setting up the advisor in a new
  project or when the user asks to init/write the advisor config.
disable-model-invocation: true
---

# Codex advisor config init

Write the default harness config to disk and show the user its absolute path.
Do not invent a different schema.

## Steps

1. Resolve the plugin root for `codex-as-advisor-guardrail`.
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
   edit: `enabled`, `model`, `effort`, `fast`, `consult_timeout_seconds`,
   `health_timeout_seconds`.
5. After they edit, suggest `/codex-advisor-health` or a new session so health
   reloads the config.
