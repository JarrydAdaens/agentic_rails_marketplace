# claude-as-review-bot-guardrail (pi host)

A wrap-up review gate for Pi. When the agent settles (`agent_settled` — the
only pi event that means "pi will not continue on its own"), an external,
read-only Claude Opus session reviews this session's changes and answers with
a one-word verdict:

- **APPROVE** — the operator gets a `ctx.ui.notify` only. The local model
  spends **zero** context on the outcome.
- **REJECT** — at most three issues, each one line of problem and one line of
  fix, hard-capped to 2,000 characters, fed back through `pi.sendUserMessage`
  so the agent can act on it.

The reviewer runs the verified advisor command line:

```
claude -p --model opus --effort high --permission-mode plan \
       --tools Read,Grep,Glob --safe-mode --no-session-persistence \
       --output-format text
```

## What the consuming project must provide

Nothing — except the changes themselves. This guardrail needs a `git` binary
on PATH, a `claude` CLI the operator has authenticated, and a working tree
with changes at settle time. If any of those are absent it stands down
silently or notifies the operator; it never wedges the session.

## Loop safety (measured, not theoretical)

`agent_settled` is **reentrant**: a probe that injected a message from the
handler produced three full agent runs, stopped only by a hard counter
(pi-agentic-ide.md §9.6). This guardrail's design follows directly:

- The **hard per-session cycle counter** (default `maxCycles: 2`) is the
  primary and only load-bearing loop guard.
- A fingerprint of `git status --porcelain` + `git diff HEAD` is a
  **secondary** guard: it catches the unchanged-tree case and nothing else —
  if the agent edits files every cycle the fingerprint differs every time and
  stops nothing. The counter is what stops the loop.
- **No** in-flight boolean and **no** `ctx.isIdle()` check exist in the
  source: both were measured returning the non-blocking value on every
  reentrant fire. They look like a backstop and provide none.

## Known limitations

1. **Print mode cannot host this guardrail.** Under `pi -p` the handler fires
   once, an injected message never runs, and the deferred send throws
   "This extension ctx is stale after session replacement or reload."
   (§9.7.) The handler checks `ctx.mode` and stands down silently in
   `"print"` — in print mode there is no review, by design, not by accident.

2. **The bash-redirect gap.** Like every other host in this repository, this
   guardrail reviews the tree as it stands at settle time; it does not
   intercept shell redirections (`>`, `>>`, `tee`) in-flight. Files the agent
   creates through `bash` redirects are only reviewed if they still exist at
   settle time, and the diff only covers *tracked* changes (`git diff HEAD`)
   plus the untracked-file list from `git status --porcelain` — untracked
   file *contents* are not in the diff.

3. **The reviewer sees only what the prompt carries.** The diff is byte-capped
   (default 60,000 bytes) and the prompt says so plainly; the reviewer is
   instructed not to approve code it did not see. Very large changesets are
   reviewed on a sample, not in full.

## Configuration

Optional, per project: `harness/claude-as-review-bot-guardrail/config.json`
(same seam as every other guardrail in this repository). Absent, empty, or
malformed means "enforce with defaults."

| Key                 | Default | Meaning                                                        |
| ------------------- | ------- | -------------------------------------------------------------- |
| `enabled`           | `true`  | `false` stands the guardrail down for this project only        |
| `maxCycles`         | `2`     | Hard per-session review budget (the loop guard)                |
| `diffBudgetBytes`   | `60000` | Byte cap on the diff carried in the review prompt              |
| `reviewBudgetChars` | `2000`  | Hard character cap on the reviewer reply before injection      |
| `timeoutSeconds`    | `300`   | Reviewer CLI timeout                                           |

## Failure policy

A review that **runs and fails** is classified with the shared
`advisor-failure` module: a **hard** failure (authentication, quota/credits,
model availability, or the CLI being unreachable) means **skip the review
entirely and notify** — never wedge, never retry into a loop. A **soft**
failure (transient, or a malformed reply) may be retried once *within* the
cycle budget. Either way the operator is told what happened.
