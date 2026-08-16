# claude-as-advisor-guardrail (pi host)

Cross-vendor advisor guardrail for **pi**. It launches the locally
authenticated Claude Code CLI as a constructive, read-only senior engineering
advisor — a plan, course correction, or completion verdict in which every
concern carries a forward path — and gates the session's first `write`/`edit`
until one consult succeeds.

Pi has no MCP and needs none: the guardrail registers exactly ONE native tool,
`consult_claude_advisor`, via `pi.registerTool()`. That replaces the entire
shell-CLI-over-stdin protocol and marker-file dance of the Cursor and Codex
hosts; the write gate just holds in-memory state that its own tool set.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| `consult_claude_advisor` tool (native to pi) | first successful consult; **disarmed** if the CLI is unreachable, a consult times out, or a consult fails with a hard cause (authentication, quota/credits, model availability) | **No** |

Install as part of the repo-root pi package (`pi install <repo>`); see the
repository `README.md`. Parameters: `task`, `stage` (`planning`, `stuck`,
`pivot-check`, `completion-review`), `approach`, `evidence`, `question`.

Command line (verified, identical to the Cursor host):
`claude -p --model opus --effort high --permission-mode plan --tools
Read,Grep,Glob --safe-mode --no-session-persistence --output-format text`,
prompt on UTF-8 stdin.

## What the consuming project must provide

- An **authenticated `claude` CLI**. The guardrail resolves it from the usual
  install locations (`%LOCALAPPDATA%\pnpm`, `%APPDATA%\npm`,
  `%USERPROFILE%\.local\bin`, `%USERPROFILE%\.claude\local`) and then `PATH`,
  without operator PATH changes; a `.cmd`/`.bat` shim is invoked through
  `cmd.exe /d /c`.
- Optionally, a config seam: `harness/claude-as-advisor-guardrail/config.json`
  (same file the other hosts use), with keys:
  - `enabled` — `false` stands the guardrail down for this project only
    (default: enforced);
  - `consult_timeout_seconds` — default `600`;
  - `reply_budget_chars` — cap on the advisor reply before it reaches the
    model, default `4000`.

## Behavior notes

- **The gate disarms when the advisor is unusable, not wedged.** A missing
  CLI, a consult timeout, or a consult that runs and fails with a HARD cause
  (authentication, quota/credits, model availability) disarms the write gate
  for the session — an unusable advisor must never deny every write.
  A SOFT failure (transient, malformed, one-off) leaves the gate armed so the
  model can fix the cause and retry. Either way the failure is reported to
  the model, never swallowed.
- **Fail open on internal errors.** A bug in this guardrail allows
  `write`/`edit` through rather than blocking them — pi's `tool_call` fails
  closed, so every handler body is wrapped.
- **Advisor failures are never silent.** Tool failures are reported to the
  model with `isError: true`; nothing is swallowed.

## Known limitations

- Gate state is in-memory and scoped to the pi process: a `/new` session in
  the same process inherits a satisfied or disarmed gate.
- The `claude` model aliases (`opus`) follow Anthropic's moving alias; the
  guardrail does not pin a dated model ID.
- Requires a Windows or POSIX environment where the `claude` CLI is
  authenticated for one-shot `-p` use.
