# Plan: Split the Marketplace Into Three Per-Host Source Roots

## Metadata

- Task Type: `REFACTOR`
- Status: `Draft`
- Owner: `Jarryd Adaens`
- Last Updated: `16 August 2026`

## Linked Context

- Milestone: `context/implementation-plans/milestone-per-ide-marketplace/` (no `context/milestones/` document exists yet; the milestone is defined by this folder)
- Story: none recorded; this plan is the story of record
- Related Plans:
  - `context/implementation-plans/milestone-cursor-guardrail-parity/remove-mcp-and-fix-cursor-bom/plan.md` — **must partially precede this plan and then be re-pathed.** Its Part A (BOM fix) lands first; its Parts B–D reference `plugins/<name>/` paths that this plan invalidates.
  - `context/implementation-plans/milestone-per-ide-marketplace/vm-release-gate-harness/plan.md` — supplies the payload-fixture capture that must happen **before** the split, and the cross-tree drift tests that make the split safe.
- Design source: `context/design.md` §4, which this plan explicitly amends.
- External Tooling: `rails-planning-phaser` (recommended before execution)

## CER

- Complexity: `5`
- Effort: `6`
- Risk: `5`
- Notes: Hand-graded. Complexity is moderate — the operation is mechanical and the per-host membership is already declared by the three catalogs, so almost nothing is a judgment call. Effort is driven by breadth: 11 folders become 24, each needing a prune pass. Risk is concentrated in one place — the split converts a loud failure mode (one edit breaks three hosts) into a silent one (one fix misses two hosts), and is only safe if the cross-tree drift tests land with it.

## Objective

Replace the single `plugins/<plugin-name>/` tree — where one payload carries three host manifests and branches on host at runtime — with three independent source roots, `plugins/claude/`, `plugins/codex/`, and `plugins/cursor/`. Each root contains only the plugins that host supports, pruned to single-host code with the host branching **deleted** rather than duplicated. Amend `context/design.md` §4, which currently mandates the opposite, and record what would have to be true to justify recollapsing later.

## Scope

### In Scope

- Create the three per-host roots and distribute all 11 existing plugins into them according to the three existing catalogs.
- Prune every copy to a single host: remove foreign manifests, foreign hook wiring, foreign documentation, and the runtime host-branching code.
- Repoint each catalog at its own subtree only.
- Preserve the harness seam name as a cross-tree invariant so a project never grows more than one config folder per plugin.
- Relocate per-plugin tests into their trees, and add root-level cross-tree contract tests that walk every root.
- Amend `context/design.md` §4 and the Layout section of `AGENTS.md` to describe the new structure and record the abandoned principle with its reversal conditions.
- Verify, before moving anything, how each vendor treats a plugin whose `name` is unchanged but whose catalog `source` path changed.

### Out Of Scope

- Any behavioral change to a guardrail. This is a structural refactor; a plugin's decisions must be byte-identical before and after, which is what the payload-replay fixtures exist to prove.
- The MCP removal and BOM fix. Those belong to the `remove-mcp-and-fix-cursor-bom` plan; the BOM fix lands **before** this plan, the MCP work lands **after** it.
- Building the VM harness. Separate plan.
- Resolving the `cursor-as-*`-in-the-Cursor-catalog overlap with `local-advisor-guardrail` (see Questions). Flagged here, decided elsewhere.

## Non-Goals

- Deduplicating the resulting triplication behind a shared library or a generation step. The split is a deliberate fork; a sync mechanism would re-create the coupling it exists to remove.
- Renaming any plugin. `name` stays stable across trees — only the catalog `source` path changes.
- Making the three trees identical. Divergence is the point; the contract tests assert **behavior**, not sameness.

## Current Understanding

### Why the current shape stopped working

`context/design.md` §4 states the governing principle directly:

> The shared artefact logic (the actual eval/guardrail scripts) should be authored **once**; only the thin per-tool registration manifests are duplicated.

That principle assumed the hosts were structurally similar enough for one payload to serve all three. In practice the payload does not merely *adapt* per host — it branches on host at runtime, in the most safety-critical file in each plugin:

```python
# plugins/codex-as-advisor-guardrail/hooks/advisor_gate.py
CLAUDE_DENY = "...Call consult_advisor (MCP) with all five fields..."
CURSOR_DENY = "...Pipe a JSON object with task, stage, approach..."
...
cursor = payload.get("hook_event_name") == "preToolUse"
...
deny = CURSOR_DENY if cursor else CLAUDE_DENY
if cursor:
    print(json.dumps({"permission": "deny", ...}))          # Cursor schema
    return
print(json.dumps({"hookSpecificOutput": {...}}))            # Claude schema
```

Two deny strings, two reply schemas, two exit conventions, one file. Editing that file for one host demonstrably risks the other, and there is no automated path that would catch it. The same pattern recurs in `advisor_marker.py` (`_is_cli_consult` reading both a top-level `command` and, post-MCP-removal, `tool_input.command`) and `advisor_context.py` (`if payload.get("hook_event_name") == "sessionStart"`).

Note the design principle was already labelled provisional: §4 says *"Proposed shape (to be validated by the reviewing agent against current vendor docs — see §7)"*, and the document is v0.2, `status: "Draft for review"`. This plan is that validation returning a negative result.

### The payoff is deletion, not duplication

Post-split, each copy of `advisor_gate.py` has one deny string, one reply schema, one exit path. The duplicated files are individually *smaller and simpler* than the shared original. This materially reduces the usual cost of triplication: the story is not "one complex file, three times" but "one complex file replaced by three simple ones."

### Membership is already declared

Each catalog states which plugins its host supports, so the distribution requires no judgment:

| Root | Count | Source catalog |
| --- | --- | --- |
| `plugins/cursor/` | 11 | `.cursor-plugin/marketplace.json` |
| `plugins/claude/` | 8 | `.claude-plugin/marketplace.json` |
| `plugins/codex/` | 5 | `.agents/plugins/marketplace.json` |

24 folders, from 11. Per-plugin membership:

| Plugin | claude | codex | cursor |
| --- | :---: | :---: | :---: |
| `jobs-done-guardrail` | ● | | ● |
| `local-advisor-guardrail` | ● | ● | ● |
| `codex-as-advisor-guardrail` | ● | | ● |
| `codex-as-critic-guardrail` | ● | | ● |
| `claude-as-advisor-guardrail` | | ● | ● |
| `claude-as-critic-guardrail` | | ● | ● |
| `cursor-as-advisor-guardrail` | ● | ● | ● |
| `cursor-as-critic-guardrail` | ● | ● | ● |
| `python-uv-guardrail` | ● | | ● |
| `readme-name-guardrail` | ● | | ● |
| `claude-home-fence-guardrail` | | | ● |

Cursor is both the largest tree and the one under heaviest churn — which is itself an argument for giving it its own room.

### Likely files and directories

- `plugins/` — the 11 existing folders, all moving.
- `.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`, `.agents/plugins/marketplace.json` — repointed at subtrees.
- `tests/test_cross_ide_guardrails.py` — `MarketplaceMatrixTests` and `test_every_catalog_source_resolves_to_matching_host_manifest` (lines 43-58) validate the current one-folder-many-manifests shape and must be rewritten to validate the new one. This is the natural home for the new cross-tree contract tests.
- `AGENTS.md` — the Layout and conventions section, and the hard rule about `.claude-plugin` / `.codex-plugin` / `.cursor-plugin` manifests living side by side.
- `context/design.md` §4, and §7's open-questions list.

### Existing behaviors to preserve

- Plugin `name` is a stable identifier; renames require an append-only `renames` map in `.claude-plugin/marketplace.json`.
- No `version` in `.claude-plugin/plugin.json`; `.codex-plugin` and `.cursor-plugin` do carry versions.
- A plugin cannot reference files outside its own folder — the install copies the folder. The split does not change this; it deepens the path by one level.
- The harness seam: `harness/<plugin-name>/config.json` inside the *consuming project*. A project is used by more than one IDE, so this path must **not** acquire a host suffix in any tree.
- Gates fail open; a missing seam degrades to a silent skip.

### Assumptions and constraints

- Each host reads only its own catalog, so the same plugin `name` appearing in all three trees cannot collide — no host ever sees two.
- The repository is public (`JarrydAdaens/agentic_rails_marketplace`), so marketplace registration by URL needs no credentials.
- Git rename detection follows only one copy; two of three trees start fresh history per plugin.

## Questions / Unknowns

- Q: Does each vendor treat a catalog entry whose `name` is unchanged but whose `source` path moved as an **update** to the installed plugin, or as a different plugin?
  Impact: Decides whether existing installs migrate cleanly or strand a stale copy with live hooks still registered. If any host treats it as new, users need an explicit uninstall-then-reinstall step, and possibly a `renames` entry — which `AGENTS.md` treats as append-only history, so it must not be spent by accident.
  Assumption: Assume it is an update, but verify on the VM before moving anything.
  Status: `OPEN`
  Answer: —

- Q: Do all hook events actually fire in `cursor-agent` CLI mode, or only `beforeShellExecution` / `afterShellExecution`?
  Impact: If `preToolUse` is IDE-only, the Cursor tree's write gate is an IDE-only feature and its `README.md` must say so. Splitting first would triplicate an inaccurate claim.
  Assumption: Assume full coverage until the harness plan's Step 1 experiment says otherwise; do not write host-capability claims into the pruned docs until it reports.
  Status: `OPEN` — owned by `vm-release-gate-harness/plan.md` Step 1
  Answer: —

- Q: Should `cursor-as-advisor-guardrail` and `cursor-as-critic-guardrail` remain in the Cursor catalog at all?
  Impact: In the Cursor tree those become Cursor consulting Cursor, which is what `local-advisor-guardrail` already does. Carrying them forward triplicates a probable redundancy.
  Assumption: Carry them forward unchanged for now — dropping a plugin is a product decision, not a refactor decision.
  Status: `OPEN`
  Answer: —

- Q: Which tree should inherit git history for each plugin?
  Impact: Only one `git mv` per plugin preserves rename detection; the other two copies begin fresh.
  Assumption: Cursor, on the grounds that it is the largest tree and under the heaviest change, so its history is the most valuable to keep readable.
  Status: `OPEN`
  Answer: —

## Execution Steps

1. **Verify vendor identity semantics before moving anything.**
   - Why: Answers the first open question, and it is the only step that can invalidate the whole approach. A path change that reads as a new plugin means every existing install strands a stale copy with registered hooks.
   - Edits: None to the repository. On the test VM: install one plugin from the current catalog, move it to a subtree on a scratch branch, re-point the catalog, run each host's marketplace update, and observe whether the install updates in place. Record the result in `## Evidence / References`.
   - Dependencies: Requires the VM from `vm-release-gate-harness`, or a manual equivalent. This is the one step that cannot be done from the repository alone.

2. **Land the BOM fix and capture payload fixtures first.**
   - Why: Both are strictly cheaper before the split. The BOM fix is one edit per plugin now and three per plugin later. The fixtures must be recorded while there is exactly one copy of each hook, so they become the shared before/after oracle proving the refactor changed no behavior.
   - Edits: None here — this step consumes Part A of `remove-mcp-and-fix-cursor-bom/plan.md` and Step 2 of the harness plan. Record both as completed preconditions before proceeding.
   - Dependencies: Blocks every step below.

3. **Create the three roots and distribute the plugins.**
   - Why: The structural move itself.
   - Edits: `git mv plugins/<name> plugins/cursor/<name>` for each of the 11 (history follows Cursor). `cp -r` from the moved copy into `plugins/claude/` and `plugins/codex/` per the membership table. Do not prune yet — a pure move, reviewable as a move.
   - Dependencies: Steps 1-2.

4. **Prune each copy to its host.**
   - Why: This is where the split earns its value; an unpruned copy is pure cost.
   - Edits: In each copy delete the two foreign `.{host}-plugin/` manifests; delete the foreign hook wiring (`cursor-hooks.json` from claude/codex trees, `hooks.json` from the cursor tree); delete `docs/hosts/*.md` for other hosts and collapse the survivor into `docs/`; delete foreign-host sections from `advisor-protocol.md` / `critic-protocol.md` and each `README.md`.
   - Dependencies: Step 3.

5. **Delete the runtime host branching.**
   - Why: The actual payoff. Each file should end up shorter than the shared original.
   - Edits: In every `hooks/*_gate.py`: delete the unused deny constant, delete the `cursor = payload.get("hook_event_name") == "preToolUse"` test, and delete the unreachable reply-schema branch. In `hooks/*_marker.py`: keep only the host's own command/tool lookup. In `hooks/*_context.py`: keep only the host's own output shape. In `hooks/*_session.py` / `*_markers.py`: drop host parameters that now have one possible value.
   - Dependencies: Step 4.

6. **Assert the refactor changed no behavior.**
   - Why: A structural refactor that silently alters a decision is the worst outcome available here.
   - Edits: Replay the Step 2 fixtures against every pruned copy and diff each decision against the pre-split recording for that host. Any difference is either a bug or a deliberate simplification that must be written down in `## Evidence / References`.
   - Dependencies: Step 5.

7. **Repoint the three catalogs.**
   - Why: Each host must resolve its own subtree and nothing else.
   - Edits: Rewrite `source` in all three catalogs to `./plugins/<host>/<name>`. Preserve every `name` exactly. Preserve the existing `renames` map in `.claude-plugin/marketplace.json` untouched.
   - Dependencies: Step 4.

8. **Freeze the harness seam as a cross-tree invariant.**
   - Why: A consuming project is used by more than one IDE. If the trees drift on the seam folder name, a project grows two configs and the second host silently reads defaults — a silent-divergence failure identical in shape to the BOM bug.
   - Edits: Confirm every tree's config resolution still targets `harness/<plugin-name>/config.json` with no host suffix, and add a contract test asserting it across all trees.
   - Dependencies: Step 5.

9. **Rebuild the root test suite as cross-tree contract tests.**
   - Why: This is the mitigation that makes the split safe. Without it the split trades a loud failure for a quiet one.
   - Edits: Rewrite `tests/test_cross_ide_guardrails.py`. Keep a structural tier (every catalog entry resolves inside its own root; every plugin folder carries exactly one host manifest; no folder references a path outside itself). Add a behavioral tier that walks `plugins/*/*/hooks/` and replays the fixtures against every gate in every tree, so a fix landing in two of three trees fails the build. Move per-plugin tests into their trees.
   - Dependencies: Steps 5-8.

10. **Amend the design documents.**
    - Why: `design.md` §4 currently mandates the opposite of what ships, and per the global rules documentation follows the behavior into the repository rather than preceding it.
    - Edits: Rewrite §4 around three per-host roots. Add a short subsection recording that the author-once principle was tried and abandoned, why (runtime host branching in the safety-critical path, no automated cross-host validation, three vendors iterating independently), and the explicit condition that would justify recollapsing — convergence of hook payload schemas and event names across all three vendors. Update the `AGENTS.md` Layout section and its side-by-side-manifests rule. Bump `metadata.version` in `design.md`.
    - Dependencies: Steps 3-9 complete and verified.

11. **Validate and record migration guidance.**
    - Why: Existing installs on the second machine need to know what to do.
    - Edits: Run `claude plugin validate .`; run the full root suite; run the VM release gate if available. Depending on Step 1's answer, add a short migration note to `README.md` telling existing users whether to update in place or uninstall and reinstall.
    - Dependencies: All.

## Validation

### Automated Checks

- `python -m pytest tests/` — structural tier plus cross-tree fixture replay.
- `python -m pytest plugins/<host>/<plugin>/tests/` for each relocated suite.
- `claude plugin validate .` from the repo root.
- Fixture-replay diff: every pruned gate returns the same decision for its host's recorded payloads as the pre-split code did.
- Structural assertion: every folder under `plugins/*/` contains exactly one `.{host}-plugin/` directory, and it matches its parent root.
- Structural assertion: no file under `plugins/` references a path containing `../`.

### Manual Checks

1. Register the marketplace fresh in each of the three IDEs on the test VM and confirm each lists exactly its own tree's plugins and no others.
2. With a plugin already installed from the pre-split catalog, run each host's marketplace update and observe whether it updates in place or strands the old copy (this is Step 1's evidence, re-confirmed against the final layout).
3. In one consuming project, confirm both Claude Code and Cursor read the same `harness/<plugin-name>/config.json` with no second folder created.

### Acceptance Criteria

- `plugins/` contains exactly three directories: `claude/`, `codex/`, `cursor/`, holding 8, 5, and 11 plugin folders respectively.
- Every plugin folder contains exactly one host manifest, matching its root.
- No `hooks/*.py` in any tree branches on host — `git grep -n "hook_event_name\" *) *== *\"preToolUse\"" plugins/` returns nothing, and no gate defines more than one deny constant.
- Every gate returns byte-identical decisions to the pre-split code for its host's recorded fixtures.
- Each of the three catalogs resolves entirely within its own root.
- The cross-tree contract test fails when a fix is deliberately reverted in exactly one tree — verified by mutation, not assumed.
- `harness/<plugin-name>/config.json` is identical across trees; no tree adds a host suffix.
- `design.md` §4 and `AGENTS.md` describe three roots, and the abandoned principle is recorded with its reversal condition.

## Risk Mitigation

- Risk: The split converts "one edit breaks three hosts" into "one fix misses two hosts." Coupling bugs are loud; drift bugs are silent, and silent is the failure mode that has actually cost time here — the cp1252 defect had two legs and the second went unnoticed for weeks because the first was assumed to be the whole problem.
  Mitigation: Step 9 is not optional and must land in the same change as the split, not after it. The cross-tree fixture replay tests behavior rather than sameness, so trees may diverge deliberately while a missed fix still fails the build. Proven by mutation in the acceptance criteria.

- Risk: A vendor treats the moved `source` path as a new plugin, stranding installed copies with live registered hooks.
  Mitigation: Step 1 answers this before anything moves, on the VM, on a scratch branch. If any host strands, ship the migration note and consider staging that host's catalog move separately.

- Risk: Two of three trees lose readable git history per plugin.
  Mitigation: Accepted. History is preserved for Cursor, the tree under heaviest change. The pre-split history remains reachable in full; only rename-following across the boundary is lost.

- Risk: Pruning silently changes a decision — for example, deleting a branch that was reachable in a case nobody remembered.
  Mitigation: Step 6 diffs every gate's decisions against the pre-split recording before the change is accepted. This is why fixture capture must precede the split.

- Risk: The `remove-mcp-and-fix-cursor-bom` plan becomes stale the moment this lands, since every path in its Parts B–D changes.
  Mitigation: Sequence explicitly — that plan's Part A first, then this plan, then re-path its Parts B–D per tree. Re-pathing is also a simplification: post-split those plugins are single-host, so much of the host-conditional work in Part B disappears. Revise that plan rather than executing it against dead paths.

- Risk: The trees drift on the harness seam name, so a project silently grows two configs.
  Mitigation: Step 8 makes it a tested invariant rather than a convention.

## Phase Split

CER 5/6/5 — below the threshold that forces a split, but the plan has one natural hard boundary worth respecting: **Step 1 (vendor identity semantics) gates everything else and requires the VM.** If the harness plan is not yet far enough along to provide it, run Step 1 manually as a standalone spike before committing to the rest. Steps 3-9 are best executed as a single reviewable change so the catalogs, the code, and the tests never disagree in an intermediate commit.

## Evidence / References

- Governing principle being abandoned: `context/design.md` §4 — *"The shared artefact logic ... should be authored **once**; only the thin per-tool registration manifests are duplicated."* Document is v0.2, `status: "Draft for review"`, and §4 is explicitly labelled a proposed shape pending validation.
- Host branching in the safety-critical path: `plugins/codex-as-advisor-guardrail/hooks/advisor_gate.py` (`CLAUDE_DENY` / `CURSOR_DENY`, `hook_event_name == "preToolUse"`, two reply schemas); `hooks/advisor_marker.py` (`_is_cli_consult`); `hooks/advisor_context.py`.
- Membership derived from `.claude-plugin/marketplace.json` (8), `.agents/plugins/marketplace.json` (5), `.cursor-plugin/marketplace.json` (11).
- Tests that encode the old shape: `tests/test_cross_ide_guardrails.py:30-58`.
- Repository is public: `https://github.com/JarrydAdaens/agentic_rails_marketplace`, `visibility: PUBLIC`. No credentials needed for marketplace registration by URL.
- Cursor CLI may only emit `beforeShellExecution` / `afterShellExecution` — community report at `https://forum.cursor.com/t/cursor-cli-doesnt-send-all-events-defined-in-hooks/148316`. **Unverified against vendor documentation**; owned by the harness plan's Step 1 experiment.
- Unverified at plan time: vendor treatment of a changed catalog `source` path with an unchanged `name`.

## Complaints / Friction

### The structure made the safest possible change feel dangerous

**What happened:** Fixing one host's write gate means editing a file that also decides the other host's write gate, with no automated check that the other host still behaves.

**Why this made the task harder:** It taxes every change with a manual cross-host review that nobody can actually perform reliably, and the tax is highest on the file where a mistake is most expensive — the gate. The practical effect is hesitation: changes that should be routine get deferred because the blast radius is unknowable.

**What was tried:** The current design deliberately chose author-once with thin per-host manifests, on the reasonable theory that the hosts were similar enough. Three vendors then iterated independently on hook event names, payload shapes, and reply schemas.

**What would improve this:** The split. But the deeper missing piece is that no test ever fed a realistic host payload to a gate and asserted the outcome — which is why one BOM defect disabled every gate in the marketplace undetected. The split reduces blast radius; only the fixtures actually detect anything.

**What I think:** The author-once principle was not wrong when written; it was invalidated by the vendors diverging. Worth recording as such in `design.md` rather than as a mistake, along with the condition that would make it right again — otherwise someone will later re-merge the trees on principle rather than on evidence.
