# Claude Advisor Protocol

Use `consult_advisor` before substantive implementation, when stuck, before a
meaningful pivot, and before declaring completion. Send `task`, `stage`,
`approach`, `evidence`, and `question`. Valid stages are `planning`, `stuck`,
`pivot-check`, and `completion-review`.

The advisor is a read-only Claude session using the latest `opus` model alias
at high effort. It returns a concise plan, course correction, or completion
verdict. In Cursor, the qualified tool is
`plugin-claude-as-advisor-guardrail-claude-as-advisor-guardrail:consult_advisor`.
