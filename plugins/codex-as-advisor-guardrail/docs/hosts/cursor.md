# Host: Cursor

- Registration: `.cursor-plugin/plugin.json` (**no** `mcpServers`)
- Hooks: `hooks/cursor-hooks.json`
- Consult: Shell → `uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py` with stdin JSON
- Unlock: `afterShellExecution` matcher containing `consult_advisor`
- Health retest: skill `codex-advisor-health` or `cli/advisor_health.py`

Cursor CLI MCP instantiation is unreliable; this host deliberately avoids MCP.
SessionStart is fire-and-forget, so health starts **pending** (writes allowed)
until the probe finishes.
