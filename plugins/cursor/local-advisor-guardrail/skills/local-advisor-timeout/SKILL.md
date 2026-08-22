---
name: local-advisor-timeout
description: View or persist the advisory native-subagent consult time budget for this project.
argument-hint: "[seconds|default|cancel]"
disable-model-invocation: true
---
# Local advisor timeout
Run `python ./cli/advisor_timeout.py --seconds <USER_VALUE> --workspace <PROJECT_ROOT>`. With no value, run with `--seconds` only and wait for a reply. Explain that this is advisory: Cursor's native Task API does not expose a plugin-controlled hard-kill timeout.
