---
name: claude-critic-remove-hooks
description: >-
  Remove claude-as-critic-guardrail entries from the user-level Cursor
  hooks.json. Use when the user asks to uninstall, unregister, or unwire the
  Claude critic hooks.
disable-model-invocation: true
---

# Claude critic remove hooks

Resolve the installed plugin root and run:

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_remove_hooks.py
```

Copy stdout verbatim, especially the `Path:` line. Only this plugin's entries
are removed. Other hooks in `~/.cursor/hooks.json` stay.

Start a new CLI session after remove.
