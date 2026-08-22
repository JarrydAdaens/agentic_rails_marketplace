---
name: local-critic-install-hooks
description: Merge local-critic hooks into the user-level Cursor hooks.json so the Cursor CLI write gate can fire.
disable-model-invocation: true
---
# Local critic install hooks

Run `uv run --no-project python ./cli/critic_install_hooks.py` from the installed plugin root. It merges only this plugin's absolute hook commands into `~/.cursor/hooks.json` and preserves other entries. Start a new Cursor CLI session.
