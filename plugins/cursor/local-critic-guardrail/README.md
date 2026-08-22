# local-critic-guardrail

A Cursor-native, adversarial local critic gate. Before the first guarded write
in a session, Cursor must complete a read-only `local-critic-*` custom
subagent consultation. The plugin does not start an MCP server or a second
Cursor CLI process.

Configuration is JSONC at
`harness/local-critic-guardrail/cursor-config.json`, deliberately host-specific
so it cannot collide with equivalent Claude or Codex configurations.

Use `local-critic-init` to create commented defaults. The controls are
`local-critic-enabled`, `local-critic-health`, `local-critic-help`,
`local-critic-init`, `local-critic-model`, `local-critic-timeout`, and
`local-critic-version`.

The model selection is Auto, Cursor Grok 4.6, Composer 2.5, Gemini 3.7 Flash,
GPT-5.4-Nano, or Kimi-K3. Cursor owns each selected model's effort defaults.

Copy this source into Cursor's local plugin directory and start a fresh Agent
session. Cursor must have `uv` and Python 3 available for the local hooks.
