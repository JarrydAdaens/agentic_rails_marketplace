---
name: codex-critic-install-hooks
description: Merge Codex-as-critic hooks into the user-level Cursor hooks.json so the Cursor CLI write gate can fire.
disable-model-invocation: true
---
# Codex critic install hooks

Resolve the installed plugin root and run `uv run --no-project python ./scripts/launch.py ./cli/critic_install_hooks.py`. Copy stdout verbatim, especially `Path:`. The command rewrites hook commands to absolute plugin paths and merges them into `~/.cursor/hooks.json` without replacing other plugin entries. Start a new Cursor CLI session.
