---
name: advisor-codex-guardrail-design
description: >-
  Design notes for the Codex advisor guard rail: the native advisor pattern
  reproduced for Codex through a bundled MCP consult tool, accepted trade-offs,
  architecture, and cost controls.
metadata:
  version: "1.0"
---

# Advisor Codex Guardrail — Design Notes

**Target:** Codex through the user's existing CLI login (no API key).
**Origin:** Extracted from `advisor-guardrail`, which paired both tools in one
plugin. Loading a Codex MCP server inside Claude Code broke on machines without
`CODEX_PLUGIN_ROOT`, so the two implementations are now separate plugins with no
shared payload. The Claude implementation is `advisor-guardrail`.

## 1. Pattern being reproduced

Anthropic's native advisor tool pairs a cheaper **executor** model with a
stronger **advisor** model that reads the transcript mid-generation and returns
strategic guidance. It is API-only and unavailable through a subscription login.
This plugin reproduces the behavioral pattern for Codex on the user's existing
quota:

- The main Codex session does the actual work.
- At decision points, the executor calls `consult_advisor`, which runs a single
  read-only `gpt-5.6-sol` inference over a structured payload.
- Advisor output is short, high-signal, and cheap relative to letting the
  advisor do the whole task.

## 2. Deviations from the native tool (accepted trade-offs)

| Native tool | This design | Why it matters |
| --- | --- | --- |
| Advisor automatically receives the full transcript | Advisor receives only the structured consult payload | **Biggest gap.** Mitigated by the mandatory payload contract (§4) and a read-only sandbox so the advisor can inspect actual files |
| Advisor runs with no tools | Advisor runs `codex exec --sandbox read-only`, so it can read the repository | Improvement over native: verifies claims against real files instead of trusting the executor's summary |
| Server-side, zero client plumbing | Client-side: bundled MCP server + hooks | Hooks make the "consult before first write" rule deterministic rather than advisory |
| Billed per-model at API rates | Draws from the existing Codex/ChatGPT quota | Consults consume quota; the 120-word brevity contract is the cost control |

## 3. Architecture

```
Codex session (executor)
│
├── SessionStart hook ───────► inject Advisor Protocol into context; clean stale markers
│
├── PreToolUse hook (apply_patch) ─► deterministic gate: deny first apply_patch
│                                    until the advisor is consulted this session
│
├── PostToolUse hook (consult_advisor) ─► touch per-session marker file
│
└── consult_advisor MCP tool ─► mcp/advisor_server.py
                                 runs: codex exec --ephemeral --sandbox read-only
                                       --model gpt-5.6-sol -c model_reasoning_effort="high"
                                 returns: ≤120-word advice block
```

Markers live in `<temp>/advisor-codex-guardrail-markers/`, keyed by session ID,
so the guardrail needs no `.gitignore` entry in the target project. Shell
writes remain advisory-only: reliably parsing shell writes is too fragile, so
they are intentionally ungated.

## 4. Consult payload contract (compensates for the transcript gap)

Every `consult_advisor` call must supply `task`, `stage`, `approach`,
`evidence`, and `question`. The native advisor sees everything; this one sees
only these fields plus the read-only workspace. The MCP server rejects a call
missing any field, and rejects a `stage` outside
`planning | stuck | pivot-check | completion-review`.

## 5. Cost controls

- Brevity contract in the advisor prompt (≤120 words) — primary lever.
- Target 2–3 consults per task, encoded in the protocol.
- Read-only sandbox means the advisor cannot spend tokens making changes.

## 6. Failure handling

Authentication, unavailable-model, missing-executable, and timeout failures are
classified into actionable tool errors rather than opaque stack traces, so the
executor can self-correct (sign in, install Codex, retry).
