---
name: codex-advisor-enabled
description: Enable or disable the Codex advisor guardrail for this project and persist the choice in JSONC.
argument-hint: "<enabled|disabled>"
disable-model-invocation: true
---
# Codex advisor enabled
Resolve the installed plugin root and project workspace, then run:
```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_enabled.py --enabled <USER_INTENT> --workspace <PROJECT_ROOT>
```
Accept `true`, `false`, `yes`, `no`, `enabled`, `disabled`, `on`, `off`, `engage`, or `disengage`. Copy stdout verbatim.
