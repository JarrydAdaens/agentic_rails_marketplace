---
name: codex-critic-health
description: >-
  Retest the Codex-as-critic guardrail health for the current session and report
  ONLINE or OFFLINE with gate status. Use when the user asks to re-enable, retry,
  or health-check the critic after quota/auth/config issues, or after returning
  to a compacted thread.
disable-model-invocation: true
---

# Codex critic health retest

Run the plugin health probe and show the user a confirmation block. Do not
improvise a different check.

## Steps

1. Resolve the plugin root for `codex-as-critic-guardrail` (installed plugin
   cache or workspace marketplace path).
2. Run the health CLI from that root (prefer the launcher):

```text
uv run --no-project python ./scripts/launch.py ./cli/critic_health.py --session-id <SESSION_ID> --workspace <PROJECT_ROOT>
```

If `uv` is unavailable:

```text
python ./scripts/launch.py ./cli/critic_health.py --session-id <SESSION_ID> --workspace <PROJECT_ROOT>
```

Use the active conversation/session id when known; otherwise pass the id the
host exposes. Use the project workspace that contains
`harness/codex-as-critic-guardrail/config.json` when present.

3. Copy the CLI stdout to the user **verbatim** (it is already the confirmation
   block). Also state plainly whether the write gate is now armed or still
   disarmed.

Expected stdout shape:

```text
Codex-as-critic health check
Result: ONLINE | OFFLINE
Model: …
Effort: …
Fast: …
Reason: …
Gate: armed (next write requires consult) | disarmed (writes allowed)
Config file: FOUND | MISSING
Config path: <absolute project harness path>
```

## After ONLINE

Tell the user the next file write will be denied until a real critic consult
succeeds (Claude: `consult_critic` MCP; Cursor: stdin JSON to
`cli/consult_critic.py`).

## After OFFLINE

Tell the user writes remain ungated for this session and to fix the Reason
(auth, quota, model, config) before retrying this skill.
