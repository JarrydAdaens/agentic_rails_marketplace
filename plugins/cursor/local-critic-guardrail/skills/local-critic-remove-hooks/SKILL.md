---
name: local-critic-remove-hooks
description: Remove local-critic hook entries from the user-level Cursor hooks.json.
disable-model-invocation: true
---
# Local critic remove hooks

Run `uv run --no-project python ./cli/critic_remove_hooks.py` from the installed plugin root. Only this plugin's `~/.cursor/hooks.json` entries are removed. Start a new Cursor CLI session.
