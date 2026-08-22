---
name: claude-advisor-remove-hooks
description: >-
  Remove claude-as-advisor-guardrail entries from the user-level Cursor
  hooks.json. Use when the user asks to uninstall, unregister, or unwire the
  Claude advisor hooks.
disable-model-invocation: true
---

# Claude advisor remove hooks

Resolve the installed plugin root and run:

```text
uv run --no-project python ./scripts/launch.py ./cli/advisor_remove_hooks.py
```

Copy stdout verbatim, especially the `Path:` line. Only this plugin's entries
are removed. Other hooks in `~/.cursor/hooks.json` stay.

Start a new CLI session after remove.
