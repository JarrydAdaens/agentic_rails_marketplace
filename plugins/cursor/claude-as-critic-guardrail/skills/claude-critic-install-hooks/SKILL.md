---
name: claude-critic-install-hooks
description: >-
  Merge claude-as-critic-guardrail into the user-level Cursor hooks.json so
  the write gate can fire in Cursor CLI. Use when the user asks to install,
  register, or wire the Claude critic hooks.
disable-model-invocation: true
---

# Claude critic install hooks

Resolve the installed plugin root and run:

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_install_hooks.py
```

Copy stdout verbatim, especially the `Path:` line. The CLI rewrites this
plugin's `hooks/cursor-hooks.json` commands to absolute plugin paths and merges
them into `~/.cursor/hooks.json` without replacing other plugins' entries.

Start a new CLI session after install. Plugin hooks from `plugins/local` do not
run in Cursor CLI until they are in that file.
