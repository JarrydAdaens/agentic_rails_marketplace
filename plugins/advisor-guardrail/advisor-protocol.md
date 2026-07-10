## Advisor Protocol

This session pairs executor models (Opus/Sonnet) with a stronger advisor: the
`advisor` subagent shipped by the `advisor-guardrail` plugin (runs on
Fable). Invoke it via the Task tool with subagent_type `advisor` (namespaced
form: `advisor-guardrail:advisor`). Consult it at decision points.
Consults are cheap relative to mistakes but expensive relative to silence —
target 2–3 per task.

### When to consult

1. **Before substantive work** — before writing or editing files, committing to an interpretation of the task, or building on an assumption. Orientation (finding files, reading what's there) is not substantive work; do it first.
2. **When you believe the task is complete** — make the deliverable durable (file written, change staged) *before* the consult.
3. **When stuck** (recurring errors, non-converging approach) or **before changing approach**.
4. On tasks longer than a few steps: at least one consult before committing to an approach and one before declaring done. Short reactive tasks dictated by tool output just read don't need repeat consults.
5. **Weight the advice seriously.** Adapt only on empirical failure or primary-source contradiction. If gathered evidence conflicts with the advice, don't silently switch — run one reconcile consult: "I found X, you suggest Y — which constraint breaks the tie?"

A PreToolUse hook denies the first Write/Edit of each session until one advisor consult has occurred. The deny message tells you what to do; this is expected behavior, not an error. Bash is not gated — do not use it to bypass the consult requirement.

### Consult payload contract

The advisor does not see your transcript. Every advisor Task prompt MUST use this structure:

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
