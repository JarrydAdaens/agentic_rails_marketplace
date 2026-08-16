# Claude Critic Protocol

Consult the critic before substantive implementation, when stuck, before a
meaningful pivot, and before declaring completion.

Do **not** expect an MCP tool. Pipe one JSON object on stdin to the plugin CLI:

```text
uv run --no-project python ./scripts/launch.py ./cli/consult_critic.py
```

JSON shape:

```json
{
  "task": "...",
  "stage": "planning",
  "approach": "...",
  "evidence": "...",
  "question": "..."
}
```

Valid stages are `planning`, `stuck`, `pivot-check`, and `completion-review`.
Run that command from a shell whose working directory (or
`AGENTIC_RAILS_WORKSPACE`) is the project root.

The critic is a read-only Claude session using the latest `opus` model alias at
high effort. It attacks the approach, but every material objection must include
a correction.

A write hook denies the first Write/Edit/StrReplace/Delete of each session
until a consult succeeds. The deny message tells you what to do; this is
expected behavior, not an error.
