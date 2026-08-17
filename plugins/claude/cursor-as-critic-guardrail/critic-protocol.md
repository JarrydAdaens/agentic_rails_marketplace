## Critic Protocol

This session pairs an executor with an antagonistic, read-only critic reached
through the local Cursor Agent CLI. Invoke it with the `consult_critic` MCP
tool. Consult it at decision points. The critic's job is to attack your
approach, not reassure you — expect objections, and treat "survives attack" as
the pass signal. Target 2–3 consultations per task.

### When to consult

1. **Before substantive work** — orient by reading first, then consult before
   writing or committing to an interpretation.
2. **When you believe the task is complete** — make the deliverable durable
   before the completion-review consult.
3. **When stuck** or **before changing approach**.
4. On tasks longer than a few steps, consult at least once before committing to
   an approach and once before declaring done.
5. Test objections against evidence. If evidence contradicts the critique, use
   one reconcile consult to identify which constraint breaks the tie.

A PreToolUse hook denies the first Write/Edit of each session until one critic
consult has occurred. Shell commands are not gated; do not use them to bypass
the requirement.

### Tenacity contract

The critic attacks the work to improve it, not to halt it. A blocker is a routing
decision, not an ending condition.

- Every material objection you get back carries a recommended correction and a
  statement of whether work can continue meanwhile. An objection without one is
  incomplete — ask for the correction.
- Hypothetical risks come back labeled as hypotheses with the test that would
  confirm them. Run the test rather than treating the hypothesis as a verdict.
- If you propose stopping, escalating, or waiting for a human, the critic will
  attack that proposal as hard as it attacks your code — whether the blocker is
  global or local, what can be isolated, what can proceed, what is reversible.
  Bring the evidence for it.

### Consult payload contract

The critic does not see your transcript. Every `consult_critic` call must
supply these five fields:

- `task` — one-paragraph statement of the overall task
- `stage` — one of `planning`, `stuck`, `pivot-check`, `completion-review`
- `approach` — current plan or the approach taken
- `evidence` — key paths, errors, test output, and discovered constraints
- `question` — the specific decision or verdict wanted

The optional sixth field, `model`, selects an exact Cursor model ID. A
successful call remembers that model in this project's
`harness/cursor-as-critic-guardrail/config.json`. Omit it to reuse the saved
project default; a project with no saved default starts with `cursor-grok-4.6-high`.

A thin payload produces a poor critique. Include concrete paths, errors, and
constraints rather than asking the critic to guess.
