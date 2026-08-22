---
name: local-advisor-help
description: Explain the native Cursor local-advisor guardrail, its subagents, controls, and gate behavior.
disable-model-invocation: true
---
# Local advisor help
Start with `python ./cli/advisor_version.py` and include its result. This Cursor-only plugin uses bundled native custom subagents, never MCP and never a second Cursor CLI process. The first write is denied until the configured `local-advisor-*` Task/Agent subagent completes. Available controls are `local-advisor-enabled`, `local-advisor-health`, `local-advisor-init`, `local-advisor-model`, `local-advisor-timeout`, `local-advisor-version`, `local-advisor-install-hooks`, and `local-advisor-remove-hooks`. Run install-hooks to merge the required absolute paths into `~/.cursor/hooks.json`, then start a fresh Cursor CLI session. Model choices are Auto, Cursor Grok 4.6, Composer 2.5, Gemini 3.7 Flash, GPT-5.4-Nano, and Kimi-K3; Cursor owns effort defaults for each model.
