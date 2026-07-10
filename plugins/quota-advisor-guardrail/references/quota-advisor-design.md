---
name: quota-advisor-design
description: >-
  Design history for the advisor guard rail: the native advisor-tool behavior
  being replicated inside Claude Code, accepted trade-offs, architecture,
  cost controls, risks, and the v2 backlog.
metadata:
  version: "1.0"
---

# Quota Advisor — Design Document

**Status:** Draft for implementation
**Target:** Claude Code on Claude Max subscription (no API key)
**Implementer:** Claude Fable 5 via Claude Code
**Author context:** Replicates the pattern of Anthropic's native API advisor tool inside Claude Code, using subagents + rules + hooks. Executors are Opus/Sonnet; advisor is Fable.

**Primary reference:** https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool
Secondary reference (subagents): https://code.claude.com/docs/en/sub-agents

---

## 1. Problem statement

Anthropic's native advisor tool pairs a cheaper **executor** model with a stronger **advisor** model that reads the full transcript mid-generation and returns strategic guidance. It is API-only (`advisor_20260301` tool type, beta header `advisor-tool-2026-03-01`) and unavailable through a Max subscription.

We want the same behavioural pattern inside Claude Code on Max quota:

- Main session runs Opus or Sonnet doing the actual work.
- At specific decision points, the main agent consults a **Fable advisor subagent** for a plan, course correction, or completion review.
- Advisor output is short, high-signal, and cheap relative to letting Fable do the whole task.

## 2. What the native tool does (behaviour to replicate)

From the advisor tool doc:

1. Executor decides when to consult; the server forwards the **full transcript** (system prompt, tools, prior turns, tool results, in-progress text) to the advisor.
2. Advisor runs one inference pass with **no tools**, under its own system prompt; only advice text returns to the executor.
3. Executor continues, informed by the advice.
4. Empirically validated timing (per the doc's best-practices section): an **early call** after initial orientation but before committing to an approach, and for hard tasks a **final call** after writes/test output exist. Around **2–3 calls per task** is the target for coding workloads.
5. Advisor output is the dominant cost driver. The doc recommends capping it (native: `max_tokens: 2048`; prompt-level: asking for guidance under ~80 words, requesting ~80% of your true ceiling because it's a soft limit).
6. Opus executors self-regulate well; over-nudging Opus to consult **reduced** pass rates in Anthropic's testing. Sonnet benefits from system-prompt timing guidance. Keep steering proportional to the executor model.

## 3. Deviations from the native tool (accepted trade-offs)

| Native tool | This design | Why it matters |
|---|---|---|
| Advisor automatically receives the full transcript | Subagent receives only the Task prompt the executor writes | **Biggest gap.** Mitigated by a mandatory structured consult payload (§5.2) and giving the advisor read-only repo tools so it can verify claims itself |
| Advisor runs with no tools | Advisor gets `Read`, `Grep`, `Glob` (read-only) | Improvement over native: the advisor can inspect actual files instead of trusting the executor's summary. Costs extra tokens; bounded by the brevity contract |
| Server-side, single request, zero client plumbing | Client-side: subagent + CLAUDE.md rules + hooks | Hooks make the "consult before first write" rule deterministic rather than advisory |
| Fable advisor returns encrypted output the client can't read | Advice is plain text in the transcript | No downside for us |
| Billed per-model at API rates | Everything draws from one Max quota pool | Fable consults burn quota faster than Sonnet work; brevity contract is the cost control |

## 4. Architecture

```
Claude Code session (executor: opus or sonnet)
│
├── CLAUDE.md rules block ─── timing guidance: when to consult
│
├── PreToolUse hook ───────── deterministic gate: deny first Write/Edit
│                             until advisor consulted this session
│
├── PostToolUse hook ──────── detects advisor Task completion,
│                             writes session marker file
│
└── Task tool ──────────────► advisor subagent (.claude/agents/advisor.md)
                              model: fable
                              tools: Read, Grep, Glob (read-only)
                              returns: ≤120-word advice block
```

## 5. Components

### 5.1 Advisor subagent — `.claude/agents/advisor.md`

```yaml
---
name: advisor
description: >
  Strategic advisor backed by a stronger model. Consult BEFORE substantive
  work (writing, editing, committing to an interpretation), when stuck
  (recurring errors, non-converging approach), when considering a change
  of approach, and once before declaring a task complete. Do not consult
  for trivial lookups or when the next action is dictated by tool output
  just read.
tools: Read, Grep, Glob
model: fable
---
```

Body (system prompt) requirements:

- Role: senior reviewer/planner. You do not implement. You return a plan, a course correction, or a completion verdict.
- **Brevity contract:** default response ≤120 words. Structure: (1) verdict/direction in one sentence, (2) the 2–4 decisions or risks that actually matter, (3) one thing to verify before proceeding. No preamble, no restating the task. This mirrors the native doc's finding that advisor output length is the main cost lever and that a soft word limit should be set below the true ceiling.
- You may use Read/Grep/Glob to verify claims in the consult payload, but cap yourself at a handful of reads. You are a checkpoint, not an explorer.
- If the consult payload is missing information you need, say exactly what's missing in one line rather than guessing.
- Calibrate advice to a mid-level engineer executing it (matches the author's existing rails-rubric-cer calibration).

### 5.2 Consult payload contract (compensates for the transcript gap)

The executor MUST structure every advisor Task prompt as:

```
TASK: <one-paragraph statement of the overall task>
STAGE: <planning | stuck | pivot-check | completion-review>
PLAN/APPROACH: <current plan or the approach taken>
EVIDENCE: <key file paths, error messages, test output, constraints discovered>
QUESTION: <the specific decision or verdict wanted>
```

Rationale: the native advisor sees everything; ours sees only this. The payload plus read-only tools closes most of the gap. Enforce the format in the CLAUDE.md rules block, not the hook (hooks can't cheaply validate prose).

### 5.3 CLAUDE.md rules block (executor-side timing guidance)

Add a rules section to the project CLAUDE.md, adapted from the doc's suggested executor system prompt for coding tasks. Core rules to encode (paraphrase; pull verbatim text from the "Suggested system prompt for coding tasks" section of the reference doc if preferred):

1. Consult the advisor **before substantive work** — before writing, before committing to an interpretation, before building on an assumption. Orientation (finding files, reading what's there) is fine to do first and is not substantive work.
2. Consult when believing the task is **complete** — and make the deliverable durable (file written, change committed) *before* the consult.
3. Consult when **stuck** (recurring errors, non-converging approach) or when **changing approach**.
4. On tasks longer than a few steps: at least one consult before committing to an approach and one before declaring done. Short reactive tasks dictated by tool output just read don't need repeat consults.
5. Weight the advice seriously; adapt only on empirical failure or primary-source contradiction. On conflict between gathered evidence and advice, don't silently switch — run one **reconcile consult** ("I found X, you suggest Y, which constraint breaks the tie?").
6. Include the consult payload contract (§5.2) verbatim so the executor formats consults correctly.
7. **Model-conditional steering:** per the doc, when the executor is Opus, keep guidance light (Opus self-regulates; over-nudging measurably hurt Opus in Anthropic's testing). When the executor is Sonnet, the full timing block applies.

### 5.4 Hook enforcement (deterministic gate)

Purpose: replicate the doc's "hard rule" — the first state-changing action on a task must be preceded by an advisor consult — as an actual guardrail rather than a suggestion.

**Marker mechanism:**
- `PostToolUse` hook on the `Task` tool: script inspects the hook's stdin JSON; if the invoked subagent is `advisor`, touch `.claude/.advisor-consulted` (include session ID from the hook payload in the filename to avoid cross-session bleed).
- `PreToolUse` hook on `Write|Edit|MultiEdit|NotebookEdit`: if the marker for the current session is absent, return `permissionDecision: deny` with a reason string telling the executor to consult the advisor first. On deny, the executor sees the reason and self-corrects.
- `SessionStart` hook (or the PreToolUse script itself): clean stale markers.

**Scope decisions:**
- Do **not** gate `Bash`. Distinguishing read-only from state-changing bash reliably requires command parsing; the doc's own carve-out (ls/cat/grep/find are fine) is easy for a model to follow but fragile for a shell script to enforce. Accept Bash as an enforcement hole; the CLAUDE.md rule still covers it advisorily.
- Gate is per-session, not per-task. A long session with multiple tasks only forces one consult. Acceptable for v1; per-task tracking would need the executor to signal task boundaries (possible later via a `/task-start` skill that deletes the marker).

**Config location:** `.claude/settings.json` hooks section; hook scripts version-controlled under `.claude/hooks/`, idempotent, executable.

### 5.5 Cost controls (quota discipline)

- Brevity contract in the advisor system prompt (§5.1) — primary lever, mirrors the doc's finding of ~7x output reduction from capping with no quality loss.
- Target 2–3 consults per task, encoded in CLAUDE.md rules.
- Advisor's read-only tool budget capped by prompt ("a handful of reads").
- No conversation-level hard cap in v1 (native tool doesn't have one either; it recommends client-side counting). If quota burn becomes a problem, extend the PostToolUse marker script to count consults and have the PreToolUse hook warn past a threshold.

## 6. Implementation plan

**Phase 1 — Advisor subagent.** Create `.claude/agents/advisor.md` per §5.1. Acceptance: `Use the advisor subagent` on a toy question returns a ≤120-word structured response, and the session confirms it ran on Fable.

**Phase 2 — CLAUDE.md rules.** Add the timing block per §5.3 including the payload contract. Acceptance: on a fresh non-trivial task, executor consults before its first write without being told, and the consult prompt matches the payload format.

**Phase 3 — Hooks.** Marker + deny gate per §5.4. Acceptance: (a) attempting a Write before any consult is denied with the instructive reason; (b) after a consult, writes proceed; (c) a second session starts clean.

**Phase 4 — Calibration pass.** Run 2–3 real tasks on Sonnet executor. Check: consult count per task (target 2–3), advisor response length, whether advice measurably changed the approach. Trim the CLAUDE.md block if Opus sessions over-consult.

## 7. Risks and open questions

1. **Frontmatter `model:` field reliability.** A reported Claude Code bug (github.com/anthropics/claude-code issue #44385, Apr 2026) had subagents ignoring frontmatter `model` and inheriting the parent model. Verify on the installed version in Phase 1 by confirming the advisor actually runs on Fable. Mitigation if broken: have the executor pass `model` explicitly on the Task invocation (per-invocation model parameter takes precedence over frontmatter). Do **not** use `CLAUDE_CODE_SUBAGENT_MODEL` — it forces all subagents to one model.
2. **Fable availability on this Max plan/version.** `fable` is a documented model alias for subagents, but confirm it resolves on the workstation's Claude Code version and plan before building on it. Fallback: `model: opus` still gives Sonnet executors a genuine capability lift (this is exactly the Sonnet-executor/Opus-advisor pairing the native doc recommends).
3. **Context gap.** If advice quality is poor, the likely cause is a thin consult payload, not the advisor. Tighten the payload contract before touching anything else.
4. **Bash enforcement hole** (§5.4). Known and accepted for v1.
5. **Per-session vs per-task gating** (§5.4). Known limitation; revisit if multi-task sessions are common.

## 8. Out of scope (v1)

- Advisor-side caching (native feature; no client-side equivalent, and subagents are fresh contexts per invocation anyway).
- Conversation-level consult budgets with hard cutoffs.
- Integration with Agentic Rails phase gates (natural v2: fire a mandatory completion-review consult at each phase boundary via the phase manifest).
