# Host: Claude Code

- Registration: `.claude-plugin/plugin.json`, `.mcp.json`
- Hooks: `hooks/hooks.json` (vendor path)
- Consult: MCP tool `consult_advisor` (five fields)
- Unlock: `PostToolUse` matcher `.*consult_advisor$`
- Launcher: `python -c` + `CLAUDE_PLUGIN_ROOT` (platform-agnostic)

Cursor-specific MCP packaging is not used on this host. Session health and
harness config are shared with Cursor via `lib/`.
