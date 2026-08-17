# cursor-as-advisor-guardrail (pi host)

Cross-vendor advisor guardrail for **pi**. It launches a read-only Cursor
agent session as a constructive, read-only senior engineering advisor — a
plan, course correction, or completion verdict in which every concern
carries a forward path — and gates the session's first `write`/`edit` until
one consult succeeds.

Pi has no MCP and needs none: the guardrail registers exactly ONE native tool,
`consult_cursor_advisor`, via `pi.registerTool()`. That replaces the entire
shell-CLI-over-stdin protocol and marker-file dance of the Cursor host; the
write gate just holds in-memory state that its own tool set.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| `consult_cursor_advisor` tool (native to pi) | first successful consult; **disarmed** if the CLI is unreachable, a consult times out, or a consult fails with a hard cause (authentication, quota/credits, model availability) | **No** |

Install as part of the repo-root pi package (`pi install <repo>`); see the
repository `README.md`. Parameters: `task`, `stage` (`planning`, `stuck`,
`pivot-check`, `completion-review`), `approach`, `evidence`, `question`.

Command line (verified against
`plugins/cursor/cursor-as-advisor-guardrail/mcp/advisor_server.py:command`),
prompt over UTF-8 stdin, never on the command line:

```
agent --print --output-format text --mode ask --sandbox disabled \
      --trust --model cursor-grok-4.6-high
```

- `--mode ask` is read-only by design — that enforces the read-only advisor
  contract.
- `--sandbox disabled` explicitly disables the OS sandbox layer, which is
  unavailable on Windows, while ask mode still enforces read-only.
- The guardrail NEVER passes `--force`, `--yolo`, `--auto-review`, or any
  automatic MCP approval.

## What the consuming project must provide

- An **authenticated Cursor `agent` CLI**. The guardrail resolves it from the
  usual install locations (`%LOCALAPPDATA%\cursor-agent`) and then `PATH`,
  without operator PATH changes; a `.cmd`/`.bat` shim is invoked through
  `cmd.exe /d /c`.
- Optionally, a config seam: `harness/cursor-as-advisor-guardrail/config.json`
  (same file the other hosts use), with keys:
  - `enabled` — `false` stands the guardrail down for this project only
    (default: enforced);
  - `model` — Cursor model id, default `cursor-grok-4.6-high` (the model id
    encodes the reasoning tier, e.g. the `…-high` suffix);
  - `effort` — accepted for seam parity with the two sibling advisors; the
    Cursor CLI takes no reasoning-effort flag, so the key is read but never
    placed on the command line;
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
- **The gate is on `write`/`edit`, not on shell redirects.** A model can
  create the same file with a redirect through `bash` (`>`, `>>`, `tee`) and
  route around the denial. Measured on pi: after a clean denial of `write`, the
  local model did exactly this unprompted, within one turn, and reported
  success. Every host in this repository shares the gap; closing it means
  extending the advisor gates to redirect-carrying `bash` segments on all of
  them, which is a separate story.
- Requires a Windows or POSIX environment where the Cursor `agent` CLI is
  authenticated for one-shot `--print` use.
