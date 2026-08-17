# claude-home-fence-guardrail

Cursor-only fence that keeps agents out of Claude Code’s home tree
(`%USERPROFILE%\.claude` / `~/.claude`). Skills, plugins, agents, rules, cache —
anything under that directory is denied for reads, searches, writes, deletes, and
shell access. The decision is a pure path/text match; it spends no LLM judgment.

This plugin is **absent from the Claude Code and Codex catalogs on purpose**.
Registering the same fence there would ban Claude from its own home.

## What the plugin registers

One Python hook (`hooks/claude_home_fence.py`), launched via the same Windows
`uv` pattern as sibling marketplace guardrails (`scripts/launch-windows.cmd` →
`uv run --no-project python …`), on:

| Event | Behavior |
| --- | --- |
| `beforeReadFile` | Deny Agent reads under Claude home (`failClosed: true`) |
| `beforeTabFileRead` | Deny Tab reads under Claude home (`failClosed: true`) |
| `preToolUse` (`Write\|StrReplace\|Delete\|Edit\|…\|Grep\|Glob\|Read`) | Deny path args that target Claude home |
| `preToolUse` (`Shell`) + `beforeShellExecution` | Deny commands that reference Claude home |
| `sessionStart` | Inject a short hard policy telling the agent the fence exists |

On install, Cursor asks you to review and trust the hooks — that prompt is the
point of the guardrail being a plugin.

## Always-JSON contract (failClosed-safe)

Cursor treats empty or invalid hook stdout as failure. With `failClosed: true`,
that bricks *every* matched tool — not just Claude-home hits. This hook therefore:

- always prints valid JSON on stdout (`permission: allow` or `deny`, or
  `additional_context` on `sessionStart`)
- treats empty or malformed stdin as **allow**, not a crash
- catches unexpected exceptions and emits **allow** (only a true Claude-home
  match denies)

`failClosed: true` still blocks if the process itself fails to start (for
example `uv` missing). Install `uv` or set `AGENTIC_RAILS_UV` to an absolute
`uv.exe` path — same requirement as the advisor/critic guardrails.

## What to expect after install

- Reading `C:\Users\<you>\.claude\skills\...\SKILL.md` is denied.
- Grepping or globbing under `~/.claude` is denied.
- Shell like `Get-Content $env:USERPROFILE\.claude\...` or `cat ~/.claude/...` is denied.
- Workspace `CLAUDE.md`, project-local `.claude/`, project-local `.agents/`, and
  anything under `~/.cursor` pass.
- The deny is the guardrail working, not an error.

Enable the plugin per project or globally through Cursor’s plugin enablement
scopes. For a local smoke test you can copy this plugin’s hook script + launcher
into `~/.cursor` and point `~/.cursor/hooks.json` at them (see the marketplace
handoff notes for the exact file list).

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
- **Windows-first launcher.** Hook commands use `launch-windows.cmd` + `uv`,
  matching sibling Cursor guardrails. The Python fence itself is portable; the
  registered command line is Windows-oriented.
- **Shell marker match.** Shell denial looks for explicit Claude-home markers
  (`~/.claude`, `%USERPROFILE%\.claude`, absolute `...\Users\...\ .claude\...`,
  etc.). Obfuscated indirection (variables invented mid-script, encoded paths)
  is out of scope for a pattern-match fence.
