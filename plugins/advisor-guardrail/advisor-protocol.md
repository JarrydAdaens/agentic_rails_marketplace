## Advisor Protocol

This session pairs an executor with a stronger, read-only advisor. Invoke the
Opus advisor subagent via Task/Agent as `advisor-guardrail:advisor`. Consult it
at decision points. Consults are cheap relative to mistakes but expensive
relative to silence — target 2–3 per task.

### When to consult

1. **Before substantive work** — before writing or editing files, committing to an interpretation of the task, or building on an assumption. Orientation (finding files, reading what's there) is not substantive work; do it first.
2. **When you believe the task is complete** — make the deliverable durable (file written, change staged) *before* the consult.
3. **When stuck** (recurring errors, non-converging approach) or **before changing approach**.
4. On tasks longer than a few steps: at least one consult before committing to an approach and one before declaring done. Short reactive tasks dictated by tool output just read don't need repeat consults.
5. **Weight the advice seriously.** Adapt only on empirical failure or primary-source contradiction. If gathered evidence conflicts with the advice, don't silently switch — run one reconcile consult: "I found X, you suggest Y — which constraint breaks the tie?"

A PreToolUse hook denies the first Write/Edit of each session until one advisor
consult has occurred. The deny message tells you what to do; this is expected
behavior, not an error. Shell commands are not gated — do not use them to bypass
the consult requirement.

### Tenacity contract

A blocker is a routing decision, not an ending condition. The advisor is built to
keep the work moving: it owes you a forward path with every concern it raises,
and it will not sanction stopping cheaply.

- Bring an obstacle as a routing question — "which of these paths is best" — not
  as a request for permission to stop.
- Expect to be interrupted if your payload shows the same approach failing twice
  without new evidence. Change approach rather than repeating it.
- Before asking the advisor to endorse stopping or escalating, be ready to state
  what you tried, what could still be completed partially, what could be deferred
  or isolated, and what independent work remains.
- Settle genuine ambiguity with the smallest experiment that produces evidence,
  rather than another round of consultation.

### Consult payload contract

The advisor does not see your transcript. Every advisor prompt MUST supply this
structure:

```
TASK: <one-paragraph statement of the overall task>
STAGE: <planning | stuck | pivot-check | completion-review>
PLAN/APPROACH: <current plan or the approach taken>
EVIDENCE: <key file paths, error messages, test output, constraints discovered>
QUESTION: <the specific decision or verdict wanted>
```

A thin payload produces poor advice. Include the concrete file paths, errors, and constraints you actually have.

### Model-conditional steering

- **Executor is Opus:** treat the timing rules as defaults and self-regulate; do not over-consult. The hook still requires one consult before the first write.
- **Executor is Sonnet or below:** follow the timing rules strictly.
