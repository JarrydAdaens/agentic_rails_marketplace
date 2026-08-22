## Advisor Protocol

This session pairs an executor with a constructive, read-only advisor. Model,
reasoning effort, fast tier, and timeouts come from
`harness/codex-as-advisor-guardrail/cursor-config.json` when present (built-in default:
`gpt-5.6-sol` / `high` / `fast false` / consult 1800s / health 90s). Create that
file with the `codex-advisor-init` skill. Consult it at decision points. The
advisor's job is to improve your approach with a forward path — expect a plan,
a course correction, or a completion verdict. Consults are cheap relative to
mistakes but expensive relative to silence — target 2–3 per task.

Session start runs a health probe. If the advisor is **offline**, the write gate
is disarmed for this session — continue working, and retest with the
`codex-advisor-health` skill when auth, quota, model, or config is fixed. If
**online**, the first write is denied until one successful consult.

### Consulting the advisor

Do **not** expect an MCP tool. Pipe one JSON object on stdin to the plugin CLI:

```text
uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py
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
5. **Engage with advice seriously.** The advisor is constructive by design; do not dismiss a concern because it is inconvenient, and do not capitulate because it is forceful. Test each concern against the evidence. If evidence contradicts the advice, run one reconcile consult: "I found X, you advise Y — which constraint breaks the tie?"

A write hook denies the first Write/Edit/StrReplace/Delete of each session while
health is online and no advisor consult has succeeded. The deny message tells you
what to do; this is expected behavior, not an error. Shell commands are not
gated — do not use them to bypass the consult requirement when the gate is
armed. If health is pending or offline, writes are allowed.

### Tenacity contract

The advisor improves the work to unblock it, not to halt it. A blocker is a
routing decision, not an ending condition.

- Every material concern you get back carries a recommended next move and a
  statement of whether work can continue meanwhile. A concern without a forward
  path is incomplete — ask for one.
- Hypothetical risks come back labeled as hypotheses with the test that would
  confirm them. Run the test rather than treating the hypothesis as a verdict.
- If you propose stopping, escalating, or waiting for a human, the advisor will
  stress-test that proposal — whether the blocker is global or local, what can
  be isolated, what can proceed, what is reversible. Bring the evidence for it.

### Consult payload contract

The advisor does not see your transcript. Every consult MUST supply all five
fields:

- `task` — one-paragraph statement of the overall task
- `stage` — one of `planning`, `stuck`, `pivot-check`, `completion-review`
- `approach` — current plan or the approach taken
- `evidence` — key file paths, error messages, test output, constraints discovered
- `question` — the specific decision or verdict wanted

A thin payload produces thin advice. Include the concrete file paths, errors,
and constraints you actually have — the advisor will probe whatever you leave
vague.
