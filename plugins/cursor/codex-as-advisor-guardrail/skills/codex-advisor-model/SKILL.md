---
name: codex-advisor-model
description: View or persist the Codex advisor model and reasoning effort for this project.
argument-hint: "[model effort]"
disable-model-invocation: true
---
# Codex advisor model
Run `uv run --no-project python ./scripts/launch.py ./cli/advisor_model.py --model <USER_VALUE> --workspace <PROJECT_ROOT>` from the installed plugin root. With no value, run it with `--model` only and present the selection screen. Accept model names or ids, efforts, compact selections such as `2a` and `6f`, and `cancel`; copy stdout verbatim.
