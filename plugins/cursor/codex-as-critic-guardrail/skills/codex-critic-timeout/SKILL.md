---
name: codex-critic-timeout
description: View or persist the Codex critic consult timeout for this project.
argument-hint: "[seconds|default|cancel]"
disable-model-invocation: true
---
# Codex critic consult timeout
With no user value, run `uv run --no-project python ./scripts/launch.py ./cli/critic_timeout.py --seconds --workspace <PROJECT_ROOT>` and wait for the user's reply. With a value, use `--seconds <USER_VALUE>`. Accept positive numbers, `fourhundred`, `default`, `cancel`, and `nevermind`; copy stdout verbatim.
