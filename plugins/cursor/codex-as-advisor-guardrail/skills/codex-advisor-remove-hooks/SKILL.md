---
name: codex-advisor-remove-hooks
description: Remove Codex-as-advisor hook entries from the user-level Cursor hooks.json.
disable-model-invocation: true
---
# Codex advisor remove hooks

Resolve the installed plugin root and run `uv run --no-project python ./scripts/launch.py ./cli/advisor_remove_hooks.py`. Copy stdout verbatim, especially `Path:`. Only this plugin's entries are removed; other `~/.cursor/hooks.json` entries remain. Start a new Cursor CLI session.
