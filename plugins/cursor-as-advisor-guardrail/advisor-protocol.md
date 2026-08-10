## Cursor Advisor Protocol

This session pairs the Claude Code executor with a helpful, read-only advisor
reached through the local Cursor Agent CLI. Invoke it with the
`consult_advisor` MCP tool. The advisor's job is to improve the work: clarify
the plan, surface material risks, suggest course corrections, and give a candid
completion verdict. Target 2–3 consultations per task.

### When to consult

1. **Before substantive work** — orient by reading first, then consult before
   writing, committing to an interpretation, or building on an assumption.
2. **When you believe the task is complete** — make the deliverable durable
   before the completion-review consult so the advisor can inspect it.
3. **When stuck** or **before changing approach**.
4. On tasks longer than a few steps, consult at least once before committing to
   an approach and once before declaring done.
5. **Weight the advice seriously.** Adapt only on empirical failure or
   primary-source contradiction. If evidence conflicts with the advice, use a
   reconcile consult to identify which constraint breaks the tie.

A PreToolUse hook denies the first Write/Edit of each session until one advisor
consult has occurred. Shell commands are not gated; do not use them to bypass
the requirement.

### Consult payload contract

The advisor does not see your transcript. Every `consult_advisor` call must
supply these five fields:

- `task` — one-paragraph statement of the overall task
- `stage` — one of `planning`, `stuck`, `pivot-check`, `completion-review`
- `approach` — current plan or the approach taken
- `evidence` — key paths, errors, test output, and discovered constraints
- `question` — the specific decision or verdict wanted

The optional sixth field, `model`, selects an exact Cursor model ID. A
successful call remembers that model in this project's
`harness/cursor-as-advisor-guardrail/config.json`. Omit it to reuse the saved
project default; a project with no saved default starts with `composer-2.5`.

A thin payload produces poor advice. Include concrete paths, errors, test
results, and constraints rather than asking the advisor to guess.
