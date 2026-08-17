# python-uv-guardrail (pi)

Deterministic "python only runs under uv" guardrail for the [Pi](https://pi.dev)
coding agent. A `tool_call` handler on the `bash` tool inspects every command
before it runs and blocks any that invoke a Python interpreter or installer
directly — `python`, `python3`, `pip`, `pip3`, or the Windows `py` launcher —
instead of through `uv`. No LLM judgment: the decision is a pure pattern
match, segment-aware like the Cursor-host sibling.

This is the pi-host sibling of `plugins/cursor/python-uv-guardrail` and
`plugins/claude/python-uv-guardrail`. The three are independent
reimplementations of the same rule: the pi copy ports the *decision logic*
from `hooks/enforce-uv-python.ps1` and drops the *transport* (stdin reading,
BOM stripping, JSON envelope), which pi's in-process hooks do not have.

## How it decides

For each bash command it splits into simple-command segments on the shell
control operators (`||`, `&&`, `;`, `|`, `&`, newlines, subshell parens);
per segment it skips inline `VAR=value` assignments and the wrappers `sudo`,
`env`, `time`, `nice`, `command`, `exec`, `builtin`, `\`; and it inspects the
leading executable with directory and `.exe` stripped. A segment led by `uv`
or `uvx` is allowed; a segment led by a blocked interpreter is denied with an
instructive reason.

Blocks with `{ block: true, reason }` and **not** `terminate`, because a
legitimate remedy exists and the reason names it:

> python-uv-guardrail: 'python' was invoked directly, without uv. Re-run it
> through uv so it uses an isolated, project-scoped environment instead of
> mutating a shared global interpreter. For example: 'uv run python <args>',
> 'uv run <script>.py', 'uv pip install <pkg>', or 'uvx <tool>'. Then retry.

The deny is the guardrail working, not an error. The behavioral tests include
`uv run python --version`, `uvx ruff`, `uv pip install x`, and a plain
`uv --version` — the guardrail must never block the remedy its own message
recommends.

## Fail open

The handler body is wrapped so an internal guardrail error allows the bash
tool through rather than blocking it. A guardrail bug must never wedge the
bash tool.

## Layout

```text
python-uv-guardrail/
├── extensions/python-uv-guardrail.ts   # the pi extension (decision logic + pi glue)
├── tests/python-uv.behavior.test.ts    # behavioral tests for the deny decisions
└── README.md
```

The decision primitives it delegates to live in `plugins/pi/shared/`
(`bash-segments.ts`, `harness-config.ts`), which is importable but deliberately
not matched by the package's extension glob.

## Adopting it in a project (optional escape hatch)

The guardrail is **active by default** wherever the extension is enabled — no
seam required. The seam exists only as an escape hatch and is shared with the
Claude and Cursor hosts, so a project never grows a second config location.
To relax or disable it in a specific project, create
`harness/python-uv-guardrail/config.json` in the project root:

```json
{ "enabled": false }
```

Other supported keys, mirroring the Cursor host:

```json
{
  "blockedPattern": "^(py|python(\\d+(\\.\\d+)?)?|pip\\d*)$",
  "allowCommands": ["^uv\\b", "^pip3\\s+freeze\\b"]
}
```

Absent, empty, or malformed config all mean "enforce with defaults".

## Installing

Pi installs the whole repository as one package (pi has no per-plugin
catalog; granularity is via `pi config` filtering):

```text
pi install "D:/Code Projects/agentic_rails/agentic_rails_marketplace"
```

or from a git source. Then toggle this extension among the others with
`pi config`.

## Tests

```text
python tests/run_pi_behavior_tests.py
```

which runs `tests/python-uv.behavior.test.ts` (and the shared-module tests)
under pi's bundled Node with native type stripping — no dev dependency.
