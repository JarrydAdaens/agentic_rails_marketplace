## Claude Critic Protocol

This session pairs an executor with an antagonistic, read-only Claude critic.
Model, reasoning effort, and timeouts come from
`harness/claude-as-critic-guardrail/cursor-config.json` when present (built-in
default: `opus` / `high` / consult 600s / health 90s). Create that file with the
`claude-critic-init` skill. Consult the critic at decision points. Its job is to
attack your approach, not to reassure you — expect objections, and treat
"survives attack" as the pass signal. Consults are cheap relative to mistakes
but expensive relative to silence — target 2–3 per task.

Session start runs a health probe. If the critic is **offline**, the write gate
is disarmed for this session — continue working, and retest with the
`claude-critic-health` skill when auth, quota, model, or config is fixed. If
**online**, the first write is denied until one successful consult.

### Consulting the critic

Do **not** expect an MCP tool. Pipe one JSON object on stdin to the plugin CLI:

```text
uv run --no-project python ./scripts/launch.py ./cli/consult_critic.py
```

JSON shape:

```json
{
  "task": "...",
  "stage": "planning",
  "approach": "...",
  "evidence": "...",
  "question": "..."
}
```

Run that command from a shell whose working directory (or
`AGENTIC_RAILS_WORKSPACE`) is the project root.

### When to consult

1. **Before substantive work** — before writing or editing files, committing to an interpretation of the task, or building on an assumption. Orientation (finding files, reading what's there) is not substantive work; do it first.
2. **When you believe the task is complete** — make the deliverable durable (file written, change staged) *before* the consult.
3. **When stuck** (recurring errors, non-converging approach) or **before changing approach**.
4. On tasks longer than a few steps: at least one consult before committing to an approach and one before declaring done. Short reactive tasks dictated by tool output just read don't need repeat consults.
5. **Engage with objections seriously.** The critic is adversarial by design; do not dismiss an objection because it is inconvenient, and do not capitulate because it is forceful. Test each objection against the evidence. If evidence contradicts the objection, run one reconcile consult: "I found X, you advise Y — which constraint breaks the tie?"

A write hook denies the first Write/Edit/StrReplace/Delete of each session while
health is online and no critic consult has succeeded. The deny message tells
you what to do; this is expected behavior, not an error. Shell commands are not
gated — do not use them to bypass the consult requirement when the gate is
armed. If health is pending or offline, writes are allowed.

### Tenacity contract

The critic attacks the work to improve it, not to halt it. A blocker is a
routing decision, not an ending condition.

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

The critic does not see your transcript. Every consult MUST supply all five
fields:

- `task` — one-paragraph statement of the overall task
- `stage` — one of `planning`, `stuck`, `pivot-check`, `completion-review`
- `approach` — current plan or the approach taken
- `evidence` — key file paths, error messages, test output, constraints discovered
- `question` — the specific decision or verdict wanted

A thin payload produces thin advice. Include the concrete file paths, errors,
and constraints you actually have — the critic will probe whatever you leave
vague.
