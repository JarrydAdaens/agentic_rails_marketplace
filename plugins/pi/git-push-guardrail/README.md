# git-push-guardrail (pi)

Deterministic "agents never push" guardrail for the [Pi](https://pi.dev)
coding agent. Agents in this repository never push to a remote — publishing
is a deliberate, human-only act. A `tool_call` handler on the `bash` tool
inspects every command before it runs and blocks any segment whose leading
executable is `git` and whose arguments contain `push`, wherever it sits in
the chain: `git push`, `git push origin main`, `git push --force`,
`git -C /some/dir push`, `x && git push`. No LLM judgment: the decision is
a pure pattern match, segment-aware.

This guardrail has no Cursor-host sibling to port from — it is new to pi —
but it reuses the shared shell-command segmentation in
`plugins/pi/shared/bash-segments.ts` exactly the way
`python-uv-guardrail` does, so a push hidden behind a chain is caught the
same way a bare `python` is.

## How it decides

For each bash command it splits into simple-command segments on the shell
control operators (`||`, `&&`, `;`, `|`, `&`, newlines, subshell parens);
per segment it skips inline `VAR=value` assignments and the wrappers `sudo`,
`env`, `time`, `nice`, `command`, `exec`, `builtin`, `\`; resolves the
leading executable with directory and `.exe` stripped; and blocks when it
is `git` and a `push` argument token follows. `git pull`, `git status`,
`echo "git push"`, and `git commit -m "push it later"` are all allowed —
a message that merely mentions push never fires.

Blocks with `{ block: true, reason, terminate: true }` — deliberately the
opposite of the remedy-carrying sibling guardrails, because there is **no**
legitimate remedy an agent may reach: the human pushes from their own
terminal. `terminate: true` is load-bearing: it was measured that it stops
the local model's retry loop, and a block without it sends the model into
wasted tool calls fighting a prohibition.

> git-push-guardrail: 'git push' is forbidden. Agents in this project never
> push to a remote: publishing is a deliberate, human-only act, and no
> alternate command reaches the same effect. Stop here, do not retry a
> variant, and ask the operator to push from their own terminal when they
> are ready.

## Boundaries

- **No per-command allowlist.** A regex escape hatch on a hard prohibition
  is an accident waiting to happen; the only config key is `enabled`.
- **No `user_bash` hook.** That event is the human typing `!git push`, and
  restraining the human is not this guardrail's job.

## Fail open

The handler body is wrapped so an internal guardrail error allows the bash
tool through rather than blocking it. Pi's `tool_call` fails **closed** by
default — an unhandled throw wedges the guarded tool for the session — so
the wrapping is mandatory, and the behavioral suite includes an
induced-internal-error case asserting the tool is allowed through.

## Layout

```text
git-push-guardrail/
├── extensions/git-push-guardrail.ts   # the pi extension (decision logic + pi glue)
├── tests/git-push.behavior.test.ts    # behavioral tests for the deny decisions
└── README.md
```

## Adopting it in a project (optional escape hatch)

The guardrail is **active by default** wherever the extension is enabled —
no seam required. The seam exists only as an escape hatch. To stand it down
in a specific project, create `harness/git-push-guardrail/config.json` in
the project root:

```json
{ "enabled": false }
```

That is the only supported key. Absent, empty, or malformed config all mean
"enforce with defaults".

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

which runs `tests/git-push.behavior.test.ts` (and the shared-module tests)
under pi's bundled Node with native type stripping — no dev dependency.
