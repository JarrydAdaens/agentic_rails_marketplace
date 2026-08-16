# Claude Advisor Protocol

Consult the advisor before substantive implementation, when stuck, before a
meaningful pivot, and before declaring completion. This host has no confirmed
write-gate hook — treat this as a voluntary discipline, not an enforced one.

Do **not** expect an MCP tool. Pipe one JSON object on stdin to the plugin CLI:

```text
uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py
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

The advisor is a read-only Claude session using the latest `opus` model alias
at high effort. It returns a concise plan, course correction, or completion
verdict.
