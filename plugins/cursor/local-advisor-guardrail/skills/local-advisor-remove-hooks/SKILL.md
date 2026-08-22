---
name: local-advisor-remove-hooks
description: Remove local-advisor hook entries from the user-level Cursor hooks.json.
disable-model-invocation: true
---
# Local advisor remove hooks

Run `uv run --no-project python ./cli/advisor_remove_hooks.py` from the installed plugin root. Only this plugin's `~/.cursor/hooks.json` entries are removed. Start a new Cursor CLI session.
