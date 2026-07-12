## Advisor Protocol

This session pairs an executor with a stronger, read-only advisor. In Claude
Code, invoke the Fable subagent via Task/Agent as
`advisor-guardrail:advisor`. In Codex, invoke the `consult_advisor` MCP tool,
backed by `gpt-5.6-sol` at high reasoning. Consult it at decision points.
Consults are cheap relative to mistakes but expensive relative to silence —
target 2–3 per task.

### When to consult

1. **Before substantive work** — before writing or editing files, committing to an interpretation of the task, or building on an assumption. Orientation (finding files, reading what's there) is not substantive work; do it first.
2. **When you believe the task is complete** — make the deliverable durable (file written, change staged) *before* the consult.
3. **When stuck** (recurring errors, non-converging approach) or **before changing approach**.
4. On tasks longer than a few steps: at least one consult before committing to an approach and one before declaring done. Short reactive tasks dictated by tool output just read don't need repeat consults.
5. **Weight the advice seriously.** Adapt only on empirical failure or primary-source contradiction. If gathered evidence conflicts with the advice, don't silently switch — run one reconcile consult: "I found X, you suggest Y — which constraint breaks the tie?"

A PreToolUse hook denies the first Claude Write/Edit or Codex `apply_patch` of
each session until one advisor consult has occurred. The deny message tells you
what to do; this is expected behavior, not an error. Shell commands are not
gated — do not use them to bypass the consult requirement.

### Consult payload contract

The advisor does not see your transcript. Every Claude advisor prompt or Codex
`consult_advisor` call MUST supply this structure (Codex uses the lower-case
fields `task`, `stage`, `approach`, `evidence`, and `question`):

```
TASK: <one-paragraph statement of the overall task>
STAGE: <planning | stuck | pivot-check | completion-review>
PLAN/APPROACH: <current plan or the approach taken>
EVIDENCE: <key file paths, error messages, test output, constraints discovered>
QUESTION: <the specific decision or verdict wanted>
```

A thin payload produces poor advice. Include the concrete file paths, errors, and constraints you actually have.

### Model-conditional steering

- **Claude executor is Opus:** treat the timing rules as defaults and self-regulate; do not over-consult. The hook still requires one consult before the first write.
- **Claude executor is Sonnet or below, or executor is Codex:** follow the timing rules strictly.
