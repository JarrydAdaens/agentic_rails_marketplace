# claude-home-fence-guardrail

Cursor-only fence that keeps agents out of Claude Code’s home tree
(`%USERPROFILE%\.claude` / `~/.claude`). Skills, plugins, agents, rules, cache —
anything under that directory is denied for reads, searches, writes, deletes, and
shell access. The decision is a pure path/text match; it spends no LLM judgment.

This plugin is **absent from the Claude Code and Codex catalogs on purpose**.
Registering the same fence there would ban Claude from its own home.

## What the plugin registers

One PowerShell script (`hooks/claude-home-fence.ps1`) on:

| Event | Behavior |
| --- | --- |
| `beforeReadFile` | Deny Agent reads under Claude home (`failClosed: true`) |
| `beforeTabFileRead` | Deny Tab reads under Claude home (`failClosed: true`) |
| `preToolUse` (`Write\|StrReplace\|Delete\|Edit\|…\|Grep\|Glob\|Read`) | Deny path args that target Claude home |
| `preToolUse` (`Shell`) + `beforeShellExecution` | Deny commands that reference Claude home |
| `sessionStart` | Inject a short hard policy telling the agent the fence exists |

On install, Cursor asks you to review and trust the hooks — that prompt is the
point of the guardrail being a plugin.

## What to expect after install

- Reading `C:\Users\<you>\.claude\skills\...\SKILL.md` is denied.
- Grepping or globbing under `~/.claude` is denied.
- Shell like `Get-Content $env:USERPROFILE\.claude\...` or `cat ~/.claude/...` is denied.
- Workspace `CLAUDE.md` and anything under `~/.cursor` pass.
- The deny is the guardrail working, not an error.

Enable the plugin per project or globally through Cursor’s plugin enablement
scopes. This machine may also run the same script from `~/.cursor/hooks.json`
for immediate local enforcement without waiting on plugin install.

## Adopting it in a project (optional escape hatch)

Active by default wherever the plugin (or user hook) is enabled. To disable in
one project without removing the fence globally, create
`harness/claude-home-fence-guardrail/config.json`:

```json
{
  "enabled": false
}
```

A missing, empty, or malformed config means “enforce with defaults.”

## Known limitations (accepted trade-offs)

- **Skill listing is not hook-controllable.** Cursor may still *list* Claude-sourced
  skills in the agent system prompt (`agent_skills`). Hooks cannot strip that
  injection. They deny the follow-through when the agent tries to read, grep,
  glob, or shell those paths, and `sessionStart` tells the agent those paths are
  banned.
- **Windows-first.** The hook command invokes `powershell`; the script is
  PowerShell 5+/7 compatible but untested off Windows.
- **Shell marker match.** Shell denial looks for explicit Claude-home markers
  (`~/.claude`, `%USERPROFILE%\.claude`, absolute `...\Users\...\ .claude\...`,
  etc.). Obfuscated indirection (variables invented mid-script, encoded paths)
  is out of scope for a pattern-match fence.
