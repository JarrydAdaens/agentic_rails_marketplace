---
name: advisor-guardrail-cross-platform-execution-briefing
description: Durable execution briefing for making advisor-guardrail compatible with Claude Code and Codex.
metadata:
  version: "1.0"
---

# Advisor Guardrail Cross-Platform Execution Briefing

## Sources

- User-provided plan, **Make `advisor-guardrail` Claude + Codex Compatible**: authoritative implementation scope, public interface, constraints, and test plan.
- `context/design.md`: marketplace lifecycle boundary and dual Claude/Codex packaging model.
- `AGENTS.md`: repository rules, native install lifecycle, naming, validation, and dirty-worktree preservation.
- `plugins/advisor-guardrail/references/advisor-design.md`: existing Claude architecture and behavioral contract that must remain intact.

## Execution

- Parallelism: 0 (serial, max 1 active subagent), because manifests, MCP registration, hooks, marker behavior, tests, and documentation share one tightly bound contract.
- Specialist persona: none required.

## Queue

1. `STEP-001` — Implement and verify the complete cross-platform advisor-guardrail slice.

## Constraints

- Preserve Claude's Fable agent behavior, existing invocation path, protocol timing, and marketplace entry semantics except where wording must truthfully describe cross-platform support.
- Add Codex `consult_advisor` backed by `codex exec --ephemeral --sandbox read-only --model gpt-5.6-sol -c model_reasoning_effort='"'"'high'"'"'` using the existing Codex login.
- Support neutral markers while recognizing legacy Claude markers.
- Gate Claude Write/Edit surfaces and Codex `apply_patch`; keep shell writes advisory-only.
- Preserve the pre-existing `.claude-plugin/marketplace.json` change for `python-uv-guardrail` and the untracked `plugins/python-uv-guardrail/` work.
- Run focused unit tests plus Claude and Codex plugin validation. Smoke tests requiring interactive trust/login may be documented if the environment cannot safely complete them.
- Worker must commit only the assigned implementation and must not absorb unrelated user changes.
