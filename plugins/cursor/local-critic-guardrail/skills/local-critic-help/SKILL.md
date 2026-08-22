---
name: local-critic-help
description: Explain the native Cursor local-critic guardrail, controls, and gate behavior.
disable-model-invocation: true
---
# Local critic help

Run `python ./cli/critic_version.py` and include its result. This Cursor-only plugin requires a read-only, adversarial `local-critic-*` Task/Agent subagent before the first guarded write. It never uses MCP or a second Cursor CLI process. Controls: `local-critic-enabled`, `local-critic-health`, `local-critic-init`, `local-critic-model`, `local-critic-timeout`, and `local-critic-version`. Configuration is `harness/local-critic-guardrail/cursor-config.json`; Cursor owns model effort defaults.
