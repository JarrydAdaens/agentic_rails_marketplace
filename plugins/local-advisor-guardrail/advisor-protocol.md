## Advisor Protocol

This session has a mandatory, read-only advisor checkpoint. Consult before the
first substantive write, when stuck, before changing approach, and before
declaring non-trivial work complete.

Invoke the advisor for this host:

- Claude Code: use the `local-advisor-guardrail:advisor` Task/Agent subagent (Opus,
  high effort).
- Codex: call the `consult_advisor` MCP tool (GPT-5.6 Sol, high reasoning).
- Cursor: call the `consult_advisor` MCP tool (Cursor Grok 4.5 High).

The first Write/Edit attempt is denied until the consultation completes. Do
not use shell commands to bypass that checkpoint.

Every consultation must provide:

```text
TASK: <overall task>
STAGE: <planning | stuck | pivot-check | completion-review>
PLAN/APPROACH: <current plan or implementation>
EVIDENCE: <paths, errors, tests, and constraints>
QUESTION: <specific decision or verdict wanted>
```

Bring blockers as routing questions. If evidence contradicts the advice, run a
reconciliation consult rather than silently switching course. Prefer the
smallest experiment that resolves genuine ambiguity.
