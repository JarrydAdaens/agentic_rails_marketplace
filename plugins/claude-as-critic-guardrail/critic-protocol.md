# Claude Critic Protocol

Use `consult_critic` before substantive implementation, when stuck, before a
meaningful pivot, and before declaring completion. Send `task`, `stage`,
`approach`, `evidence`, and `question`. Valid stages are `planning`, `stuck`,
`pivot-check`, and `completion-review`.

The critic is a read-only Claude session using the latest `opus` model alias at
high effort. It attacks the approach, but every material objection must include
a correction. In Cursor, the qualified tool is
`plugin-claude-as-critic-guardrail-claude-as-critic-guardrail:consult_critic`.
