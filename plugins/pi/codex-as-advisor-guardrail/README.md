# codex-as-advisor-guardrail (pi host)

Cross-vendor advisor guardrail for **pi**. It launches an ephemeral,
read-only Codex CLI session as a constructive, read-only senior engineering
advisor — a plan, course correction, or completion verdict in which every
concern carries a forward path — and gates the session's first `write`/`edit`
until one consult succeeds.

Pi has no MCP and needs none: the guardrail registers exactly ONE native tool,
`consult_codex_advisor`, via `pi.registerTool()`. That replaces the entire
shell-CLI-over-stdin protocol and marker-file dance of the Cursor host; the
write gate just holds in-memory state that its own tool set.

| How to consult | Unlock | MCP? |
| --- | --- | --- |
| `consult_codex_advisor` tool (native to pi) | first successful consult; **disarmed** if the CLI is unreachable, a consult times out, or a consult fails with a hard cause (authentication, quota/credits, model availability) | **No** |

Install as part of the repo-root pi package (`pi install <repo>`); see the
repository `README.md`. Parameters: `task`, `stage` (`planning`, `stuck`,
`pivot-check`, `completion-review`), `approach`, `evidence`, `question`.

Command line (verified against
`plugins/cursor/codex-as-advisor-guardrail/lib/advisor_consult.py:command`),
prompt on UTF-8 stdin via the trailing dash:

```
codex exec --ephemeral --skip-git-repo-check --sandbox read-only \
           --model gpt-5.6-sol -c model_reasoning_effort="high" -
```

`--sandbox read-only` is what enforces the read-only advisor contract and
`--ephemeral` is what keeps the consult out of Codex's session history — both
are carried over deliberately.

## What the consuming project must provide

- An **authenticated `codex` CLI**. The guardrail resolves it from the usual
  install locations (`%LOCALAPPDATA%\Programs\OpenAI\Codex\bin`,
  `%LOCALAPPDATA%\OpenAI\Codex\bin`, `%APPDATA%\npm`) and then `PATH`,
  without operator PATH changes; a `.cmd`/`.bat` shim is invoked through
  `cmd.exe /d /c`.
- Optionally, a config seam: `harness/codex-as-advisor-guardrail/config.json`
  (same file the other hosts use), with keys:
  - `enabled` — `false` stands the guardrail down for this project only
    (default: enforced);
  - `model` — default `gpt-5.6-sol`;
  - `effort` — one of `minimal`, `low`, `medium`, `high`, `xhigh`; default
    `high` (an unknown value falls back to the default rather than producing
    a broken flag);
  - `consult_timeout_seconds` — default `1800`;
  - `reply_budget_chars` — cap on the advisor reply before it reaches the
    model, default `4000`.

## Behavior notes

- **The gate disarms when the advisor is unusable, not wedged.** A missing
  CLI, a consult timeout, or a consult that runs and fails with a HARD cause
  (authentication, quota/credits, model availability) disarms the write gate
  for the session — an unusable advisor must never deny every write, which is
  exactly what an exhausted Codex quota would otherwise do. A SOFT failure
  (transient, malformed, one-off) leaves the gate armed so the model can fix
  the cause and retry. Either way the failure is reported to the model, never
  swallowed.
- **Fail open on internal errors.** A bug in this guardrail allows
  `write`/`edit` through rather than blocking them — pi's `tool_call` fails
  closed, so every handler body is wrapped.
- **Advisor failures are never silent.** Tool failures are reported to the
  model with `isError: true`; nothing is swallowed.

## Known limitations

- **The consult path is UNVERIFIED pending quota.** The Codex quota on the
  development machine is exhausted, so a live consult could not be run. The
  guardrail is built against the verified command line and the
  failure/disarm path is tested; the success path must be re-checked when
  quota returns.
- Gate state is in-memory and scoped to the pi process: a `/new` session in
  the same process inherits a satisfied or disarmed gate.
- Requires a Windows or POSIX environment where the `codex` CLI is
  authenticated for one-shot `exec` use.
