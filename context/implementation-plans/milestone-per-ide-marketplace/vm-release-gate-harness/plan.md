# Plan: VM Release-Gate Harness for the Marketplace

## Metadata

- Task Type: `FEATURE`
- Status: `Draft`
- Owner: `Jarryd Adaens`
- Last Updated: `16 August 2026`

## Linked Context

- Milestone: `context/implementation-plans/milestone-per-ide-marketplace/`
- Story: none recorded; this plan is the story of record
- Related Plans:
  - `context/implementation-plans/milestone-per-ide-marketplace/split-plugins-by-host/plan.md` — consumes this plan's Step 1 (hook-event coverage) and Step 2 (payload fixtures), and owns the offline cross-tree replay tests that sit in front of this gate.
  - `context/implementation-plans/milestone-cursor-guardrail-parity/remove-mcp-and-fix-cursor-bom/plan.md` — the defect class this harness exists to catch.
- External Tooling: `rails-spike` (Step 1), `rails-planning-phaser` (required before execution)

## CER

- Complexity: `8`
- Effort: `8`
- Risk: `6`
- Notes: Hand-graded. Complexity is high because the harness spans two machines, three vendor CLIs with undocumented plugin-lifecycle surfaces, and a nondeterministic component (a language model) that must be made to produce a deterministic assertion. Effort is a full build from zero — no CI, no VM, no telemetry seam exists today. Risk is dominated by one meta-failure: a harness that reports PASS because nothing ran is indistinguishable from a harness that reports PASS because everything worked, and that is precisely the failure mode that hid the BOM defect. **Run `rails-planning-phaser` before execution.**

## Objective

Build a checked-in, reproducible release gate that drives a Hyper-V Windows 11 guest — with Claude Code, Codex, and Cursor installed and authenticated against real subscriptions — through a full validation cycle: revert to a golden checkpoint, uninstall and verify-clean any existing marketplace state, install the marketplace at a specific commit, run probe sessions that force each guardrail to fire, collect structured hook telemetry, and emit a machine-readable verdict tying "this marketplace is functional" to a specific marketplace commit and a specific set of IDE versions. Plus the daily golden-image refresh that keeps the guest current without baking in an untested IDE update.

## Scope

### In Scope

- A Hyper-V guest (Windows 11) on the local host, with all three IDEs installed and logged in against real subscriptions.
- A transport layer over **PowerShell Direct**, so no guest networking, SSH keys, or firewall rules are required.
- Golden-image lifecycle: daily IDE update, IDE-health smoke test, two-slot checkpoint rotation, revert after every gate run.
- A clean stage that uninstalls all marketplace state per IDE and asserts cleanliness with concrete file and config assertions.
- An install stage that registers the marketplace from the public git URL at a pinned commit and installs the plugins under test.
- A probe runner that starts real sessions designed to trigger each guardrail, plus the negative cases where a guardrail must *not* fire.
- A hook telemetry seam shipped in plugin code, off by default, that makes hook behavior observable independently of model output.
- A reporter producing `report.json` and `report.md` with three-valued per-scenario verdicts and the environment triple that produced them.
- Proof that the harness fails when it should, by mutation.

### Out Of Scope

- GitHub Actions or any hosted runner. Rejected: a hosted runner cannot hold authenticated subscriptions, so it can only test the parts that matter least.
- Redirected config directories (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `CURSOR_CONFIG_DIR`). Rejected: `CLAUDE_CONFIG_DIR` is undocumented and could stop redirecting after any update, and a redirected profile is not the code path real usage exercises.
- Docker. Rejected: Linux containers cannot reproduce Windows-only encoding defects, and if any hook event proves IDE-only, the gate needs a GUI a container cannot provide.
- The offline fixture-replay tests. Those live in `split-plugins-by-host/plan.md` Step 9; this plan only supplies the fixtures.
- Automating the Cursor **GUI**. If Step 1 shows events that fire only in the IDE, this plan documents the coverage gap rather than closing it.

## Non-Goals

- Running the gate on every edit. This burns three real subscriptions' quota per run; it is a release gate, not a save hook.
- Testing model *quality* — whether the advice is good. The harness tests whether the guardrail mechanism fires, denies, unlocks, and cleans up.
- Making the guest reproducible from scratch automatically. The image is built once by hand and maintained by the refresh cycle; a full unattended rebuild is a later concern.

## Current Understanding

### Why this shape, and what was rejected

The bug class being chased is environment-specific: a Windows-only UTF-8 BOM on hook stdin that made every gate silently fail open, and before it two legs of cp1252 mojibake. These reproduce only in a real Windows profile running the real CLIs. Every cheaper environment was considered and rejected on fidelity grounds, recorded above in Out Of Scope.

Hyper-V on the same host was chosen over a separate LAN box specifically because **PowerShell Direct** (`Invoke-Command -VMName`) needs no network path at all — it works through the hypervisor, survives broken guest networking, and shares one PowerShell surface with checkpoint control (`Checkpoint-VM`, `Restore-VMCheckpoint`). A self-hosted GitHub runner was rejected outright: this repository is public, and GitHub's own guidance is that self-hosted runners should almost never be used with public repositories because any fork can open a PR that executes code on the runner.

### The central design problem: making a language model produce a deterministic assertion

To test a write gate the harness must run a session that attempts a write. But the model may use a shell redirect instead of the Write tool, may ask a clarifying question, may phrase a refusal in any number of ways. Asserting on response text produces a test that fails for reasons unrelated to the plugin, which is worse than no test because it trains the reader to ignore red.

The resolution is to **assert on hook telemetry, never on agent output**. Every hook appends a structured record to a run log; the harness asserts against that log. This is deterministic regardless of what the model said, and it yields a distinction that is otherwise invisible:

| Telemetry | Meaning |
| --- | --- |
| gate record present, `decision: deny` | Guardrail worked |
| gate record present, `decision: allow` | Guardrail ran and let it through — real failure |
| **no gate record at all** | The event never fired — a different failure entirely |

That third row is the BOM bug's signature and the open Cursor headless question, and this design detects both for free.

A fourth outcome must also be modeled: the probe session never attempted a write, so the gate was never reached. That is **INCONCLUSIVE**, not PASS. Collapsing it into PASS would rebuild the exact silent-success failure this harness exists to prevent.

### The telemetry seam

`AGENTIC_RAILS_HOOK_LOG` names a JSONL path. When unset, hooks skip logging silently — matching the existing repository rule that a missing seam degrades to a silent skip, never an error. When set, every hook appends one record:

```json
{"ts": "...", "plugin": "...", "host": "...", "hook": "advisor_gate",
 "event": "preToolUse", "session": "...", "decision": "deny", "reason": "..."}
```

This is shipped code, not test-only code, so the harness observes the same path users run. It belongs in each tree's shared stream module beside the BOM-tolerant reader, so one edit per tree covers every hook in that tree.

### Likely files and directories

- `tests/release-gate/` — new. Deliberately **not** `harness/`, which in this ecosystem means per-project plugin config inside a *consuming* project; reusing that name at the marketplace root would collide with an established convention.
  - `run-release-gate.ps1` — host entry point
  - `transport/vm-session.ps1` — PowerShell Direct wrapper, credential resolution
  - `image/refresh-golden-image.ps1`, `image/smoke-test.ps1` — daily cycle
  - `guest/clean-marketplaces.ps1`, `guest/install-marketplaces.ps1`, `guest/run-probes.ps1`
  - `probes/<host>/<plugin>.json` — declarative probe definitions
  - `report/build-report.py` — JSONL to `report.json` / `report.md`
  - `fixtures/<host>/<event>.bin` — byte-exact recorded payloads, shared with the offline tier
- `plugins/*/*/hooks/*_streams.py` — gains the telemetry writer.
- `tests/test_cross_ide_guardrails.py` — the offline tier that runs in front of this gate (owned by the split plan).

### Existing behaviors to preserve

- A missing seam is a silent skip. Telemetry off by default must not change a single decision.
- Gates fail open. Telemetry must never introduce a failure path that could block a write.
- Plugins cannot reference files outside their own folder.

### Assumptions and constraints

- Host is Windows 11 Pro with Hyper-V; guest is Windows 11 with integration services enabled (PowerShell Direct requires both).
- The repository is public, so marketplace registration by URL needs no credentials on the guest.
- Guest credentials for PowerShell Direct are read from Windows Credential Manager on the host and never committed.
- Every gate run consumes real quota on three subscriptions; Claude Pro limits are the binding constraint.

## Questions / Unknowns

- Q: Which hook events actually fire in each host, and does that differ between CLI and GUI?
  Impact: Decides what is testable at all. A community report says `cursor-agent` CLI emits only `beforeShellExecution` and `afterShellExecution`, dropping `preToolUse` and `sessionStart`. If true, the Cursor write gate cannot be exercised headlessly, and is an IDE-only feature — which is a product claim in three READMEs, not merely a harness limitation.
  Assumption: Assume reduced CLI coverage until measured. Do not write host-capability claims anywhere until Step 1 reports.
  Status: `OPEN` — Step 1
  Answer: —

- Q: Do all three CLIs support non-interactive marketplace and plugin install, update, and uninstall?
  Impact: The entire clean/install cycle depends on it. `claude plugin validate` is known to exist; the full lifecycle surface for Codex and Cursor is unverified. If any host requires interaction, that host's cycle needs a different mechanism or manual intervention.
  Assumption: Assume `claude` supports it, and treat Codex and Cursor as unknown until Step 3.
  Status: `OPEN` — Step 3
  Answer: —

- Q: Where does each IDE persist installed-marketplace and installed-plugin state, and what exactly does "clean" mean per host?
  Impact: "Verify clean" needs concrete assertions, not a vibe. Without them the clean stage can report success while leaving hooks registered.
  Assumption: `~/.claude/plugins/` for Claude Code; `~/.codex/` and `~/.cursor/` for the others — to be enumerated on the guest rather than guessed.
  Status: `OPEN` — Step 3
  Answer: —

- Q: How is auth liveness checked per IDE without burning meaningful quota?
  Impact: A reverted checkpoint faithfully restores expired tokens every run. Without a cheap liveness probe this surfaces as dozens of confusing plugin failures instead of one clear "re-authenticate the VM."
  Assumption: A minimal prompt with a hard token cap per IDE, or a status/whoami subcommand if one exists.
  Status: `OPEN` — Step 6
  Answer: —

- Q: Do hooks launched by an IDE inherit machine-level environment variables set by the harness on the guest?
  Impact: If not, `AGENTIC_RAILS_HOOK_LOG` never reaches the hook and the harness sees no telemetry — which would read identically to "the event never fired."
  Assumption: Assume inheritance works, verify explicitly in Step 7 with a trivial always-fires hook before building anything on top.
  Status: `OPEN` — Step 7
  Answer: —

## Execution Steps

1. **SPIKE: measure hook-event coverage per host and per mode.** *(run `rails-spike`)*
   - Why: Constrains everything downstream and may change product claims. Cheapest possible experiment for the highest-value unknown.
   - Edits: A throwaway hook that appends its event name to a file, wired to every event each host supports. Run once under each CLI in print/headless mode and once in each GUI. Produce a coverage matrix: host × mode × event × fired. No production edits.
   - Dependencies: Needs the guest from Step 4, or can be run on the host machine directly if faster.

2. **Capture byte-exact payload fixtures.**
   - Why: They are the oracle for the offline tier and the before/after proof for the split, and they must be recorded while exactly one copy of each hook exists. This is the step that makes offline testing trustworthy — the BOM lives in these bytes, so the regression is caught by construction rather than by someone remembering to prepend it.
   - Edits: A capture hook writing raw stdin **bytes** (never decoded text) to `tests/release-gate/fixtures/<host>/<event>.bin`, plus a sidecar recording host, IDE version, and OS. Commit the fixtures.
   - Dependencies: Step 1 (so capture only targets events that actually fire). **Blocks the split plan.**

3. **Enumerate the plugin lifecycle surface per IDE.**
   - Why: Answers two open questions and determines whether the clean/install cycle is scriptable at all.
   - Edits: On the guest, document each host's non-interactive commands for marketplace add/remove and plugin install/update/uninstall, and enumerate every path and config key that changes when a plugin is installed. Record as `tests/release-gate/README.md`. This becomes the specification the clean and install stages assert against.
   - Dependencies: Step 4.

4. **Build the guest.**
   - Why: Everything else runs on it.
   - Edits: Hyper-V Windows 11 guest with integration services enabled. Install `claude`, `codex`, `cursor-agent` plus the Cursor IDE, `python`, `uv`, `git`. Authenticate all three against the real subscriptions. Take the initial golden checkpoint. Not a repository change — record the build steps in `tests/release-gate/README.md` so the image is rebuildable.
   - Dependencies: none.

5. **Build the transport module.**
   - Why: One seam between host and guest, so a topology change later is a single-file change.
   - Edits: `transport/vm-session.ps1` wrapping `Invoke-Command -VMName` and guest file transfer, with credentials resolved from Windows Credential Manager on the host. Expose exactly: run-script, copy-in, copy-out, checkpoint, restore. Never accept a credential as a parameter and never write one to disk.
   - Dependencies: Step 4.

6. **Build the golden-image lifecycle.**
   - Why: Determinism, and protection against baking a broken IDE update into the image.
   - Edits: `image/refresh-golden-image.ps1` runs update → `image/smoke-test.ps1` → checkpoint **only on smoke pass**, with two-slot rotation retaining the previous checkpoint until the new one passes. `smoke-test.ps1` asserts each CLI launches, reports a version, and is still authenticated, and fails with an explicit "re-authenticate the VM" message distinguishable from any plugin failure. Record IDE versions into the image metadata for the report's environment triple.
   - Dependencies: Step 5.

7. **Ship the hook telemetry seam.**
   - Why: The mechanism that makes every later assertion deterministic.
   - Edits: Add an appender to each tree's shared stream module honoring `AGENTIC_RAILS_HOOK_LOG`; silent no-op when unset; never raises, never affects a decision. Call it from every gate, marker, and context hook. **First verify the env var actually reaches a hook process on the guest** with a trivial always-fires hook before wiring the rest.
   - Dependencies: Step 4; ideally after the split so it is added once per tree.

8. **Build the clean stage.**
   - Why: Uninstall is a product behavior of a marketplace, not merely harness setup. Reverting to a checkpoint instead of testing uninstall means never testing it — and a plugin that installs cleanly but uninstalls badly strands live hooks in a user's config.
   - Edits: `guest/clean-marketplaces.ps1` removes all marketplace and plugin state per host, then asserts cleanliness against the Step 3 specification: cache directories absent, no marketplace entry in any config, no hooks registered. Emits its own telemetry records so clean is a graded scenario in the report, not silent infrastructure.
   - Dependencies: Steps 3, 5.

9. **Build the install stage.**
   - Why: Installs the artifact under test at a known commit.
   - Edits: `guest/install-marketplaces.ps1` registers the marketplace from the public git URL pinned to a commit SHA, installs the plugins for that host, and asserts the inverse of the clean assertions. Records the resolved SHA for the report.
   - Dependencies: Steps 3, 8.

10. **Build the probe runner and probe definitions.**
    - Why: Forces each guardrail to fire.
    - Edits: `probes/<host>/<plugin>.json` declaring scenario, prompt, tool constraints, and the expected telemetry record. Include negative scenarios (the gate must *not* fire after a successful consult; must *not* fire when health is offline) — a guardrail that always denies is as broken as one that never does. `guest/run-probes.ps1` executes each in a scratch workspace, with constrained tools (e.g. `--tools Write`) and a trivially unambiguous prompt to make the write attempt near-certain. Never assert on response text.
    - Dependencies: Steps 7, 9.

11. **Build the reporter.**
    - Why: Turns telemetry into the verdict that lets a marketplace version be marked functional.
    - Edits: `report/build-report.py` emits `report.json` and `report.md` with a three-valued verdict per scenario — `PASS` / `FAIL` / `INCONCLUSIVE` — where a probe that never attempted the gated action is INCONCLUSIVE and never PASS. Every report carries the environment triple: marketplace commit SHA, the three IDE versions, and the golden-image id. "Functional" is a claim about that triple, not about the repository in the abstract.
    - Dependencies: Step 10.

12. **Prove the harness fails when it should.**
    - Why: The meta-risk. A harness that always reports PASS is worse than none, and this exact defect class — a check that silently succeeds — is what produced the BOM situation.
    - Edits: Mutation runs on a scratch branch: revert the BOM fix in one tree only (expect FAIL for that tree, PASS for the others); break one plugin's uninstall (expect a clean-stage FAIL); disable one hook's registration entirely (expect INCONCLUSIVE, not PASS). Record all three outcomes as evidence. The harness is not accepted until it fails all three ways correctly.
    - Dependencies: Step 11.

13. **Document and wire into the workflow.**
    - Why: Makes it usable and states its limits honestly.
    - Edits: `tests/release-gate/README.md` covering image rebuild, the daily refresh cadence, how to run the gate, how to read a report, roughly what a run costs in quota, and the coverage gaps from Step 1 (any IDE-only events, any host lacking non-interactive lifecycle). Add the gate to the release checklist in `AGENTS.md`, explicitly as a release gate rather than a per-change check.
    - Dependencies: Step 12.

## Validation

### Automated Checks

- Offline tier (owned by the split plan) passes before the gate is invoked at all.
- A full gate run completes and emits `report.json` with no scenario in an unknown state.
- Two consecutive gate runs from the same checkpoint at the same commit produce identical verdicts — determinism is itself an asserted property.
- Clean-stage assertions pass on a guest that has never had the marketplace installed, and again after an install/uninstall cycle.
- Mutation runs from Step 12 produce the three expected failures.

### Manual Checks

1. Sever guest networking and confirm PowerShell Direct still reaches it — the reason this topology was chosen.
2. Let the golden image go stale past token expiry and confirm the smoke test fails with the re-authenticate message rather than as plugin failures.
3. Inspect one probe's raw telemetry by hand and confirm it matches the reporter's verdict.
4. Confirm `AGENTIC_RAILS_HOOK_LOG` unset produces byte-identical hook decisions to the same run with it set.

### Acceptance Criteria

- One command on the host runs the full cycle — revert, clean, verify clean, install, probe, report, revert — with no interactive prompt.
- Every guardrail in every tree has at least one positive and one negative probe scenario, or a written reason in `README.md` why it cannot be probed.
- No verdict is derived from model response text; every verdict derives from hook telemetry or filesystem assertions.
- A probe that did not reach the gated action reports INCONCLUSIVE, never PASS.
- The harness is proven to fail three distinct ways by mutation, with evidence recorded.
- Reports name the marketplace commit SHA, the three IDE versions, and the image id.
- Telemetry disabled leaves every hook decision byte-identical.
- No credential appears anywhere in the repository.
- Coverage gaps are documented rather than silently absent.

## Risk Mitigation

- Risk: The harness reports PASS because nothing ran. The defect class that already cost the most here.
  Mitigation: Three-valued verdicts with INCONCLUSIVE as a first-class outcome; the "no gate record" telemetry case; and Step 12's mutation proof, which is a hard acceptance criterion rather than a nice-to-have.

- Risk: A host does not support non-interactive plugin lifecycle, blocking the clean/install cycle.
  Mitigation: Step 3 discovers this before anything is built on top. If a host cannot be scripted, ship the other two and document the gap; a two-host gate is worth far more than none.

- Risk: `preToolUse` fires only in the Cursor GUI, so the flagship guardrail cannot be exercised headlessly.
  Mitigation: Step 1 measures it first. If confirmed, document the gap plainly, correct the affected READMEs, and treat GUI automation as separate work rather than smuggling it into this plan. Note the harness still detects the *absence* of the event, which is itself the finding.

- Risk: Each run burns real quota across three subscriptions; Claude Pro is the binding limit.
  Mitigation: Positioned explicitly as a release gate. The offline fixture tier runs on every edit and catches the entire encoding and drift class for free. Record approximate per-run cost in `README.md` so the trade-off is visible at the moment of use.

- Risk: Reverting restores expired auth tokens faithfully, every run.
  Mitigation: The smoke test in Step 6 fails with a message that cannot be mistaken for a plugin failure, and the golden image is only replaced on smoke pass.

- Risk: A broken IDE update gets baked into the golden image, and a day of runs fails for upstream reasons.
  Mitigation: Update → smoke → checkpoint ordering, with two-slot rotation keeping the last known-good image until the new one passes.

- Risk: The telemetry seam introduces a failure path in a safety-critical hook.
  Mitigation: Append-only, exception-swallowing, silent no-op when unset; validated by asserting byte-identical decisions with telemetry on and off.

- Risk: The harness becomes a conversation rather than a script — reproducible only when an agent drives it the same way twice.
  Mitigation: Every stage is a checked-in script producing structured output. An agent's role is to invoke, read the report, and fix code — never to *be* the runner. Determinism across two consecutive runs is an asserted property.

## Phase Split

CER 8/8/6 — above threshold on complexity and effort. **Run `rails-planning-phaser` before execution.** The natural seams:

- **Phase 1 — Measure (Steps 1-3).** Answers every blocking unknown, produces the fixtures the split plan needs, requires almost no new code. Highest value per unit of effort in the whole plan; do this first regardless of what follows.
- **Phase 2 — Guest and transport (Steps 4-6).** Infrastructure, independently verifiable.
- **Phase 3 — Telemetry (Step 7).** Small but touches shipped plugin code in every tree; best landed with, or immediately after, the split.
- **Phase 4 — Cycle (Steps 8-11).** The bulk of the build.
- **Phase 5 — Proof and documentation (Steps 12-13).** Not optional; Phase 4 without Phase 5 is a harness nobody should trust.

## Evidence / References

- Config-directory redirection was evaluated and rejected: `CODEX_HOME` is documented (`https://developers.openai.com/codex/environment-variables`); `CURSOR_CONFIG_DIR` is documented (`https://cursor.com/docs/cli/reference/configuration`); `CLAUDE_CONFIG_DIR` works but is undocumented, with open issues including `https://github.com/anthropics/claude-code/issues/33430` and `https://github.com/anthropics/claude-code/issues/3833`. Rejected on the grounds that an undocumented redirect is not the code path real usage exercises.
- Self-hosted runners rejected for a public repository per GitHub's own guidance: `https://docs.github.com/en/actions/reference/security/secure-use`, `https://github.com/orgs/community/discussions/26722`, and `https://www.sysdig.com/blog/how-threat-actors-are-using-self-hosted-github-actions-runners-as-backdoors`. Repository confirmed `visibility: PUBLIC`.
- Reduced Cursor CLI hook coverage, community report, **unverified against vendor docs**: `https://forum.cursor.com/t/cursor-cli-doesnt-send-all-events-defined-in-hooks/148316`. Cursor hooks reference: `https://cursor.com/docs/hooks`. Headless mode: `https://cursor.com/docs/cli/headless`.
- The defect this harness exists to catch: `https://forum.cursor.com/t/hooks-not-firing-cannot-have-guardrails/168407/6`.
- Naming decision: `tests/release-gate/`, not `harness/` — the latter already means per-project plugin config inside a consuming project (`AGENTS.md`, project-seams rule).
- Unverified at plan time: hook-event coverage per host and mode; non-interactive plugin lifecycle support for Codex and Cursor; per-host installed-state locations; environment-variable inheritance into hook processes; per-host auth liveness checks.

## Complaints / Friction

### There is no way to know a guardrail works without spending money

**What happened:** Validating a hook end to end requires a real authenticated session against a paid subscription, on a real Windows profile, in a real IDE. Every cheap option — hosted CI, containers, redirected config directories — fails on fidelity for the exact bug class that keeps occurring.

**Why this made the task harder:** It makes the feedback loop expensive enough that it will not be run often, which is how a defect survives in eleven plugins for months. It also makes the validation environment a standing maintenance cost: three IDEs updating near-daily, three subscriptions to keep authenticated, one image to keep current.

**What was tried:** Config-directory redirection (undocumented for Claude Code, so unreliable); hosted runners (cannot hold subscriptions, and self-hosted is unsafe on a public repo); containers (wrong OS for the bug class).

**What would improve this:** Vendors shipping a documented hook-replay or dry-run mode — feed a payload, get the decision, no session and no quota. Absent that, the recorded-fixture tier is the closest available substitute and is why it is worth building even though it does not exercise the real IDE.

**What I think:** The expense is real but the split of labor is right. The fixtures catch the encoding and drift class for free on every edit; the VM catches integration and lifecycle failures at release time only. What must not happen is the VM gate becoming the *only* check — it is too expensive to run often enough to be a safety net, and treating it as one would recreate exactly the gap it was built to close.
