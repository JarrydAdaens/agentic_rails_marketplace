# python-uv-guardrail

Deterministic "python only runs under uv" guardrail, delivered as a marketplace
plugin. A PreToolUse hook on the Bash tool pattern-matches every command before
it runs and denies any that invoke a Python interpreter or installer directly —
`python`, `python3`, `pip`, `pip3`, or the Windows `py` launcher — instead of
through `uv`. The denial carries a retry instruction, so the agent self-corrects
to `uv run ...` / `uv pip install ...` rather than mutating a shared global
interpreter. It spends no LLM judgment: the decision is a pure pattern match.

**Claude Code only.** The payload is built on Claude Code's PreToolUse
permission-decision schema, so this plugin ships no Codex manifest and is absent
from the Codex catalog.

**Why PowerShell, not Python?** A Python-interpreted hook for a guardrail whose
entire purpose is "never invoke bare python" is a bootstrap paradox — if the
machine has no clean global `python` on PATH (the very reason to standardize on
uv), the hook itself could not run. The hook is PowerShell, guaranteed present
on the Windows-first target and free of any interpreter it is meant to police.

## What the plugin registers

One PreToolUse hook matched to `^Bash$`
(`hooks/enforce-uv-python.ps1`, PowerShell). For each Bash command it splits the
command into simple-command segments on shell control operators (`;`, `&&`,
`||`, `|`, `&`, newlines, subshell parens), skips leading environment
assignments and wrapper commands (`sudo`, `env`, `time`, `nice`, `command`,
`exec`), and inspects the leading executable of each segment. A segment led by
`uv` or `uvx` is allowed; a segment led by a blocked interpreter is denied via a
`permissionDecision: "deny"` with an instructive reason. On install, Claude Code
asks you to review and trust the hook — that prompt is the point of the guardrail
being a plugin.

## What to expect after install

Once enabled, `python script.py` is denied with a reason telling the agent to
re-run it as `uv run python script.py`; `pip install requests` is denied in
favor of `uv pip install requests`. `uv run python ...`, `uvx ...`, and
non-Python commands pass untouched. The deny is the guardrail working, not an
error. Enable the plugin per project or globally through the standard `/plugin`
enablement scopes.

## Adopting it in a project (optional escape hatch)

Unlike a verifier that needs project-specific commands, this guardrail is
**active by default** wherever the plugin is enabled — no seam required. The seam
exists only as an escape hatch. To relax or disable it in a specific project,
create `harness/python-uv-guardrail/config.json`:

```json
{
  "enabled": true,
  "blockedPattern": "^(py|python(\\d+(\\.\\d+)?)?|pip\\d*)$",
  "allowCommands": ["^python --version$"]
}
```

- `enabled` (default `true`): set `false` to switch the guardrail off in this
  project without disabling the plugin globally — for a legitimately non-uv
  codebase.
- `blockedPattern` (optional): override the regex matched against each leading
  executable's basename. Defaults to the pattern shown above.
- `allowCommands` (optional): a list of regexes matched against the full command
  string; any match is allowed through. Use it to permit narrow exceptions such
  as `python --version` probes.

A missing, empty, or malformed config means "enforce with defaults." The config
is ordinary project configuration and should be committed; the guardrail writes
no runtime output, so no `.gitignore` entry is needed.

## Known limitations (accepted trade-offs)

- **Leading-token detection only.** A Python call hidden inside a wrapper's
  quoted argument — `bash -c "python x.py"`, `sh -c '...'` — is not caught,
  because the segment's leading executable is `bash`, not `python`. This mirrors
  the deliberate simplicity of a pattern-match guardrail; broadening it to parse
  quoted sub-commands invites false positives (e.g. `echo "run python later"`).
- **Windows-first.** The hook command invokes `powershell`; the script is
  PowerShell 5+/7 compatible but untested off Windows.
- **Interpreter/installer scope.** It gates `python`/`pip`/`py`, not every tool
  that happens to be Python-based (`pytest`, `ruff`, ...). Those are best run via
  `uv run <tool>` by convention; extend `blockedPattern` per project if you want
  them gated too.
