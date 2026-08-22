## Local Critic Protocol

Before the first substantive write, invoke the configured read-only
`local-critic-*` Cursor Task/Agent subagent. It must critically challenge the
proposed work; do not use shell commands to bypass this checkpoint.

Provide the critic:

```text
TASK: <overall task>
STAGE: <planning | implementation | pivot-check | completion-review>
PROPOSAL: <planned or completed work>
EVIDENCE: <paths, errors, tests, and constraints>
QUESTION: <specific flaw, risk, or verdict to investigate>
```

Act on material findings, or explain why evidence disproves them. The critic is
read-only and may inspect only the files needed to test its claims.
