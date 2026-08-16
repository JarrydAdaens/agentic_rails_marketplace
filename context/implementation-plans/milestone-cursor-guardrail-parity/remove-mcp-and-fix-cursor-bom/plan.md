# Plan: MCP-Free Cross-Vendor Guardrails and the Cursor Windows BOM Fix

## Metadata

- Task Type: `STORY`
- Status: `Draft`
- Owner: `Jarryd Adaens`
- Last Updated: `16 August 2026`

## Linked Context

- Milestone: `context/implementation-plans/milestone-cursor-guardrail-parity/` (no `context/milestones/` document exists in this repository yet — the milestone is currently defined only by this folder)
- Story: none recorded; this plan is the story of record
- Backlog source: none
- Dictation source: none
- Related Plans: none
- External Tooling: `rails-planning` (this plan), `rails-planning-phaser` (recommended before execution — see `## Phase Split`), `rails-spike` (required for Step 12)

## CER

- Complexity: `7`
- Effort: `8`
- Risk: `6`
- Notes: Hand-graded at plan time, not via `rails-grade-cer`. Complexity is driven by four plugins × three hosts × two transports, with one host (Codex) having no proven hook mechanism anywhere in the repository. Effort is dominated by `claude-as-*`, which must gain an entire `lib/` + `cli/` + `skills/` architecture it does not currently have. Risk is the combination of removing a working transport (MCP) before its replacement is proven on every host, and depending on undocumented Cursor and Claude Code hook payload shapes. This exceeds a single-unit threshold — run `rails-planning-phaser` before execution.

## Objective

Make `codex-as-advisor-guardrail`, `codex-as-critic-guardrail`, `claude-as-advisor-guardrail`, and `claude-as-critic-guardrail` completely free of MCP, consulting their backend model through a shell-invoked CLI on every host, and make their Cursor write gates actually enforce on Windows by fixing the UTF-8 BOM defect Cursor confirmed on the forum. Repo-wide, every hook that parses a JSON payload from stdin must tolerate a leading BOM.

## Scope

### In Scope

- Remove MCP transport (`.mcp.json`, `mcp.json`, `mcp/`, and every manifest reference) from the four named plugins.
- Port the existing `codex-as-*` shell-CLI consult transport to every host of all four plugins: Cursor, Claude Code, and Codex.
- Build the missing `lib/`, `cli/`, `scripts/launch.py`, and `skills/` layers for `claude-as-advisor-guardrail` and `claude-as-critic-guardrail`, including the pending/online/offline health-probe model that replaces their MCP-liveness gate.
- Fix BOM-intolerant stdin parsing in every plugin in this repository that receives a Cursor hook payload, not only the four named ones (per direction taken on 16 August 2026).
- Make the fail-open path in each gate hook diagnosable rather than silent.
- Update the three marketplace catalogs, per-plugin `README.md`, protocol markdown, host docs, `CHANGELOG.md`, and `VERSION` files to match what actually ships.
- Add a regression test that feeds a BOM-prefixed payload to each gate hook and asserts the gate still denies.

### Out Of Scope

- Any change to `local-advisor-guardrail`'s or `cursor-as-*`'s MCP transport. Those plugins keep MCP; only their BOM handling is touched.
- Changing advisor/critic prompt wording, model defaults, effort levels, or the five-field consult contract.
- Rewriting the marker/health state machine's semantics. The `claude-as-*` plugins adopt the existing `codex-as-*` state machine as-is rather than a new design.
- Publishing to the forum, or installing the marketplace on the second machine. Those follow the trial.

## Non-Goals

- Building a generic transport abstraction shared across all plugins. Each plugin stays self-contained because a plugin cannot reference files outside its own folder (`AGENTS.md`, hard rules).
- Deduplicating `windows_runtime.py`, `advisor_session.py`, and friends across plugin folders. The duplication is forced by the install-copies-the-folder constraint and is deliberate.
- Retrofitting `jobs-done-guardrail`, `python-uv-guardrail`, `readme-name-guardrail`, or `claude-home-fence-guardrail` with anything beyond the BOM fix.

## Current Understanding

### The BOM defect (root cause, confirmed)

Cursor's `deanrie` confirmed on the forum thread that on Windows the CLI prefixes the JSON payload it pipes to a hook over stdin with a UTF-8 BOM (`﻿`), so a plain `JSON.parse` / `json.load` raises. Their recommended fix is to strip the BOM before parsing, and they noted it applies to hooks imported from `~/.claude` as well. It is a tracked Cursor issue with no ETA, so the workaround is permanent for our purposes.

In this repository the defect lands precisely here:

```python
# plugins/codex-as-advisor-guardrail/hooks/advisor_gate.py:51-56
force_utf8()
try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    print("Codex advisor hook received invalid input; allowing the write.", file=sys.stderr)
    sys.exit(0)
```

`force_utf8()` (`hooks/advisor_streams.py:29-38`) reconfigures the stream as `utf-8`, which decodes a BOM into a literal `﻿` character rather than discarding it. `json.load` then raises `JSONDecodeError`, the handler fires, and the gate exits 0 — allowing the write. The guardrail therefore reports as installed and running while never denying anything. This is exactly the "defensive error handler silently allows" behavior the forum reply described.

**Critical detail for the fix:** `force_utf8()` reconfigures stdin *and* stdout with the same encoding. `utf-8-sig` strips a BOM when decoding but **emits** one when encoding. Applying `utf-8-sig` to both streams would prefix our JSON reply with a BOM and break Cursor's parse of our decision. Stdin must become `utf-8-sig`; stdout must stay `utf-8`.

### The MCP situation, per plugin

| Plugin | Hosts | Cursor transport today | Claude transport today | Codex transport today |
| --- | --- | --- | --- | --- |
| `codex-as-advisor-guardrail` | Claude, Cursor | Shell CLI (`cli/consult_advisor.py`) — already MCP-free | MCP (`.mcp.json` → `mcp/advisor_server.py`) | n/a (no `.codex-plugin/`) |
| `codex-as-critic-guardrail` | Claude, Cursor | Shell CLI (`cli/consult_critic.py`) — already MCP-free | MCP | n/a |
| `claude-as-advisor-guardrail` | Codex, Cursor | MCP (`mcp.json` → `launch-windows.cmd`) | n/a (no `.claude-plugin/`) | MCP (`.mcp.json`) |
| `claude-as-critic-guardrail` | Codex, Cursor | MCP | n/a | MCP |

The two `codex-as-*` plugins are the reference implementation. `docs/hosts/cursor.md` already records the reason: *"Cursor CLI MCP instantiation is unreliable; this host deliberately avoids MCP."* This story generalizes that decision to every host of all four plugins.

The two `claude-as-*` plugins are far less developed and have **no** CLI transport, no `lib/`, no `skills/`, no tests, and no health probe. Worse, their gate is structurally coupled to MCP:

```python
# plugins/claude-as-advisor-guardrail/hooks/advisor_gate.py
if not has_live_server(host, workspace):
    reason = f"Claude advisor gate is inactive because {host} has not registered consult_advisor ..."
```

`has_live_server` (`hooks/advisor_markers.py`) checks for a PID file written by the MCP server on `tools/list`. Delete MCP and that gate becomes permanently fail-open. It must be replaced by the `codex-as-*` pending/online/offline health-probe model, not merely deleted.

### Likely files and directories

- `plugins/{codex,claude}-as-{advisor,critic}-guardrail/` — the four targets.
- `plugins/codex-as-advisor-guardrail/lib/`, `cli/`, `scripts/launch.py`, `skills/` — the source pattern to port (≈1,000 lines across `advisor_config.py`, `advisor_consult.py`, `advisor_health.py`, `advisor_session.py`, `windows_runtime.py`).
- `plugins/*/hooks/*_streams.py` — the `force_utf8` helper, duplicated per plugin.
- `plugins/claude-home-fence-guardrail/hooks/claude_home_fence.py:71,104-108` — its own inline `force_utf8` plus `sys.stdin.read()` → `json.loads`.
- `plugins/local-advisor-guardrail/hooks/advisor_gate.py:46`, `advisor_marker.py:30`, `advisor_context.py:32` — bare `json.load(sys.stdin)` with **no** `force_utf8` at all.
- `.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`, `.agents/plugins/marketplace.json` — the three catalogs `AGENTS.md` requires be kept in sync.
- `tests/test_cross_ide_guardrails.py` — root matrix tests; `AdapterContractTests.NEW` (lines 62-66) asserts an MCP handshake against `advisor_server.py` for `codex-as-advisor-guardrail`, `claude-as-advisor-guardrail`, and `claude-as-critic-guardrail`. Removing MCP breaks this test by construction; it must be rewritten, not deleted.
- `plugins/{codex,cursor}-as-*/tests/test_{advisor,critic}_server.py` — per-plugin MCP handshake tests with the same problem.

### Existing behaviors to preserve

- Gates fail **open**, never closed. A broken hook must not stop the human from working. The BOM fix must keep that property while making the failure visible.
- The three-state health model: `pending` (probe unfinished, writes allowed), `online` (deny until consult), `offline` (writes allowed with a message). Cursor's `sessionStart` is fire-and-forget, which is why `pending` exists.
- The five-field consult contract (`task`, `stage`, `approach`, `evidence`, `question`) and the four valid stages.
- The harness seam: per-project config at `harness/<plugin-name>/config.json`, and a missing seam degrades to a silent skip.
- No `version` field in `.claude-plugin/plugin.json`; `.codex-plugin/plugin.json` and `.cursor-plugin/plugin.json` do carry versions and need bumps.

### Interfaces and data contracts

- **Cursor `preToolUse` reply:** `{"permission": "deny"|"allow", "user_message": ..., "agent_message": ...}` on stdout.
- **Claude Code `PreToolUse` reply:** `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}`.
- **Cursor unlock event:** `afterShellExecution`, matcher on the command string containing `consult_advisor`.
- **Claude Code unlock event:** currently `PostToolUse` with matcher `.*consult_advisor$` (an MCP tool name). Post-change it must match `Bash` and inspect the command — and Claude Code nests the command under `tool_input.command`, not a top-level `command` key, which `advisor_marker.py:37` currently assumes.

### Assumptions and constraints

- `uv` is on PATH, or resolvable by `scripts/launch.py` / `launch-windows.cmd`'s registry-PATH restoration. Both `codex` and `claude` CLIs are installed and authenticated.
- A plugin folder is copied wholesale into a per-tool cache on install, so no `../` references and no shared code across plugin folders.
- The forum's BOM report is specific to Windows. The fix (`utf-8-sig` on decode) is a no-op on platforms without a BOM, so it can be applied unconditionally.

## Questions / Unknowns

- Q: Does the Codex CLI support a pre-tool-use hook mechanism through a plugin manifest at all?
  Impact: This decides whether `claude-as-*` on Codex gets a real enforcing write gate or only an advisory protocol instruction. There is **no** Codex hook wiring anywhere in this repository — no `codex-hooks.json`, no `hooks` key in any `.codex-plugin/plugin.json` — so today Codex support is MCP-only across every plugin. Removing MCP without a hook mechanism removes enforcement on that host entirely.
  Assumption: Until proven otherwise, assume Codex has no usable pre-write hook, and that the Codex host will ship consult-capable but gate-less.
  Status: `OPEN`
  Answer: —

- Q: What exact payload does Cursor send on `afterShellExecution`, and does it include `exit_code`?
  Impact: `advisor_marker.py:_is_cli_consult` prefers `exit_code`, falls back to a `status`/`result` string, then to sniffing the output text for failure words. If none of those keys are present, a *failed* consult unlocks the write gate, which silently defeats the guardrail in the opposite direction from the BOM bug.
  Assumption: Assume `exit_code` may be absent and keep the layered fallbacks, but log which branch decided the unlock.
  Status: `OPEN`
  Answer: —

- Q: With no MCP tool in Cursor's UI, will the agent reliably run the shell consult command from the injected protocol text alone?
  Impact: This is the whole premise. The `codex-as-*` Cursor host already relies on it, so there is prior art, but it has been running with a fail-open gate because of the BOM bug — meaning it has never actually been under enforcement pressure. Post-fix behavior is genuinely unverified.
  Assumption: Assume the deny message (which states the exact command) plus the `sessionStart` protocol injection is sufficient, and treat the first Cursor trial as the test.
  Status: `OPEN`
  Answer: —

- Q: Does Claude Code's `PostToolUse` matcher operate on the tool name only, requiring command inspection inside the hook, or can it match command content?
  Impact: Determines whether the Claude Code unlock is `"matcher": "Bash"` plus in-hook filtering, or something narrower.
  Assumption: Assume tool-name-only matching, so `advisor_marker.py` must read `tool_input.command`.
  Status: `OPEN`
  Answer: —

## Execution Steps

### Part A — BOM fix (do this first; it is independently valuable and unblocks any real Cursor testing)

1. **Split `force_utf8` into a BOM-tolerant stdin and a BOM-free stdout.**
   - Why: `utf-8-sig` strips a BOM on decode but emits one on encode. Applying it to both streams replaces one bug with another.
   - Edits: In each `hooks/*_streams.py`, replace the single-encoding loop with an explicit `force_utf8_io()` that reconfigures `sys.stdin` as `utf-8-sig` and `sys.stdout`/`sys.stderr` as `utf-8`. Add a `read_hook_payload()` helper in the same module that reads stdin, strips a residual leading `﻿` defensively, and returns the parsed dict — so no hook calls `json.load(sys.stdin)` directly again.
   - Dependencies: none.

2. **Route every stdin-parsing hook through `read_hook_payload()`.**
   - Why: One parse path means one place to get the encoding right.
   - Edits: `codex-as-advisor` (`advisor_gate.py:53`, `advisor_marker.py:57`, `advisor_context.py:54`), `codex-as-critic` (same three), `cursor-as-advisor` (`advisor_gate.py:35`, `advisor_marker.py:27`, `advisor_context.py:33`), `cursor-as-critic` (`critic_gate.py`, `critic_context.py`), `claude-as-advisor` (`advisor_gate.py:13`, `advisor_marker.py`, `advisor_context.py` — the latter two have no `force_utf8` at all), `claude-as-critic` (same). Add the helper to `local-advisor-guardrail`, which has no `force_utf8` anywhere, and to `claude-home-fence-guardrail`, which has its own inline copy at `claude_home_fence.py:71`.
   - Dependencies: Step 1.

3. **Audit the remaining plugins for stdin parsing and apply the same fix.**
   - Why: Scope was set to all Cursor-hooked plugins, and the grep so far has not covered `jobs-done-guardrail`, `python-uv-guardrail`, or `readme-name-guardrail`.
   - Edits: Grep each for `json.load(sys.stdin)` / `sys.stdin.read()`; apply the Step 1 helper wherever a Cursor hook payload is parsed. Discovery step — the exact file list is not yet confirmed for these three.
   - Dependencies: Step 1.

4. **Make the fail-open path loud.**
   - Why: The BOM bug was invisible for as long as it was because the handler swallowed the cause. Keep failing open — that is deliberate — but stop hiding why.
   - Edits: In each gate's parse-failure branch, print the exception type and the first ~40 bytes of the raw payload as a `repr` to stderr before allowing. Never print payload contents to stdout, which carries the decision JSON.
   - Dependencies: Steps 1-3.

5. **Add the BOM regression test.**
   - Why: This is the defect the whole story exists to fix; it must not silently return.
   - Edits: In each plugin's `tests/test_hooks.py`, add a case that pipes `b"\xef\xbb\xbf" + payload` to the gate with health forced `online` and asserts the reply is a `deny`, not an allow. Where a plugin has no test file (`claude-as-*`), create one modeled on `plugins/codex-as-advisor-guardrail/tests/test_hooks.py`.
   - Dependencies: Steps 1-4.

### Part B — Remove MCP from `codex-as-advisor-guardrail` and `codex-as-critic-guardrail`

6. **Delete the MCP transport.**
   - Why: The Cursor UI surfaces `.mcp.json` and tries to instantiate a server that this host is documented never to use.
   - Edits: Remove `.mcp.json`, `mcp/`, and the stale `mcp/__pycache__/` from both plugins. Add `__pycache__/` coverage to `.gitignore` if the committed `.pyc` files are tracked (verify with `git ls-files`).
   - Dependencies: Part A complete, so the Cursor host is known-good before the Claude host changes.

7. **Move the Claude Code host onto the shell CLI.**
   - Why: One transport per plugin; MCP is gone.
   - Edits: In `hooks/hooks.json`, change the `PostToolUse` matcher from `.*consult_advisor$` to `Bash`. In `hooks/advisor_marker.py` (and the critic twin), extend `_is_cli_consult` to read the command from `tool_input.command` as well as the top-level `command` key, so it works under both hosts. Rewrite `CLAUDE_DENY` in `advisor_gate.py:25-29` to name the shell command instead of "(MCP)".
   - Dependencies: Step 6.

8. **Update the protocol and host docs to match.**
   - Why: `AGENTS.md` and the global rules both forbid describing behavior that is not yet in the repository — so this lands after Step 7, not before.
   - Edits: `advisor-protocol.md` / `critic-protocol.md` — replace the "Host: Claude Code / Invoke the MCP tool" section with the same shell-CLI instruction the Cursor section carries. `docs/hosts/claude.md` — rewrite the Registration/Consult/Unlock lines. `docs/architecture.md` — drop the `mcp/advisor_server.py` row and the "Claude-only JSON-RPC MCP transport" wording. `.claude-plugin/plugin.json` description — remove "consult_advisor MCP" and "Cursor uses a Shell CLI instead of MCP" (there is no longer a contrast to draw). `README.md`, `CHANGELOG.md`, `VERSION`, `.cursor-plugin/plugin.json` version bump.
   - Dependencies: Step 7.

9. **Retire the MCP tests.**
   - Why: `tests/test_advisor_server.py` and `test_critic_server.py` handshake against a file that no longer exists.
   - Edits: Replace each with a CLI-transport test that pipes a five-field JSON object to `cli/consult_advisor.py` with the backend stubbed, asserting validation rejects a missing field and a bad `stage`. Remove the `.mcp.json` assertions (`test_advisor_server.py:52`, `test_critic_server.py:52,58`).
   - Dependencies: Step 7.

### Part C — Port the full architecture into `claude-as-advisor-guardrail` and `claude-as-critic-guardrail`

10. **Build the `lib/` layer.**
    - Why: These plugins have no config, health, session, or consult layer. Without it, removing MCP leaves the gate permanently fail-open via `has_live_server`.
    - Edits: Copy and adapt `codex-as-advisor-guardrail/lib/` — `advisor_config.py` (harness seam at `harness/claude-as-advisor-guardrail/config.json`), `advisor_session.py` (marker/health state), `advisor_health.py` (probe), `windows_runtime.py` (PATH restore; a 209-line variant already exists at `mcp/windows_runtime.py` and can be moved up), and `advisor_consult.py` built around the `claude` CLI invocation currently at `mcp/advisor_server.py:52-63` (`claude -p --model opus --effort high --permission-mode plan --tools Read,Grep,Glob --safe-mode --no-session-persistence --output-format text`). Preserve `CLAUDE_ADVISOR_TIMEOUT_SECONDS` and the 600s default. Mirror all of it for the critic.
    - Dependencies: Part B, so the pattern is settled before it is duplicated twice more.

11. **Build `cli/`, `scripts/launch.py`, and `skills/`; rewrite the hooks.**
    - Why: The consult entry point, a cross-platform launcher to replace the Windows-only `launch-windows.cmd`, and the user-invoked health/init/help skills the protocol text refers to.
    - Edits: Add `cli/consult_advisor.py`, `cli/advisor_health.py`, `cli/advisor_init.py`, `scripts/launch.py`, and `skills/claude-advisor-{health,init,help}/SKILL.md` (critic equivalents likewise). Rewrite `hooks/advisor_gate.py` to use `health_state()` instead of `has_live_server()`, and delete `has_live_server` / `mark_server_ready` / `clear_server_ready` / `server_path` from `hooks/advisor_markers.py`. Rewrite `hooks/advisor_context.py` to run the health probe and emit the presence block. In `hooks/cursor-hooks.json`, change `afterMCPExecution` to `afterShellExecution` with matcher `consult_advisor`, and change every command from `cmd.exe /d /c .\scripts\launch-windows.cmd` to the cross-platform `uv run --no-project python ./scripts/launch.py` form used by `codex-as-*`.
    - Dependencies: Step 10.

12. **SPIKE: establish whether Codex supports a pre-write hook.** *(run `rails-spike`)*
    - Why: This is the one genuinely unknown thing in the plan and it gates Step 13. No Codex hook wiring exists anywhere in this repository, so removing MCP may remove enforcement on that host entirely. Answer it with the smallest experiment rather than by reasoning.
    - Edits: No production edits. Produce a spike record naming the mechanism (or its absence) and the recommended Codex wiring.
    - Dependencies: Step 11.

13. **Wire the Codex host per the spike result, and delete MCP from `claude-as-*`.**
    - Why: Completes the MCP removal across all three hosts.
    - Edits: Delete `.mcp.json`, `mcp.json`, `mcp/`, and `scripts/launch-windows.cmd` from both plugins. Strip `"mcpServers"` from `.cursor-plugin/plugin.json` and `.codex-plugin/plugin.json`, and remove `"MCP"` from the `.codex-plugin` `interface.capabilities` array. If the spike found a Codex hook mechanism, add `hooks/codex-hooks.json` and reference it; if not, ship the Codex host consult-capable but gate-less and **say so plainly** in `README.md` and `.codex-plugin/plugin.json`'s description rather than implying enforcement.
    - Dependencies: Step 12.

14. **Rewrite the `claude-as-*` protocol and docs.**
    - Why: `advisor-protocol.md` is currently 12 lines and names a Cursor MCP tool id (`plugin-claude-as-advisor-guardrail-...:consult_advisor`) that will not exist.
    - Edits: Replace with the fuller `codex-as-*` protocol structure — health-state explanation, per-host consult instructions, when-to-consult, tenacity contract, payload contract. Add `docs/architecture.md` and `docs/hosts/{cursor,codex}.md`. Add `README.md` sections for the harness seam and known limitations. Add `CHANGELOG.md` and `VERSION`, and bump `.cursor-plugin` / `.codex-plugin` versions.
    - Dependencies: Step 13.

### Part D — Repository-level reconciliation

15. **Fix the root cross-IDE tests.**
    - Why: `tests/test_cross_ide_guardrails.py:62-66` asserts an MCP handshake for three of the four plugins and will fail by construction.
    - Edits: Replace `AdapterContractTests` with a CLI-transport contract test covering all four plugins. Keep `MarketplaceMatrixTests` intact — the host matrix is unchanged if the Codex host survives Step 13; if it does not, update `test_each_lead_can_install_both_roles_from_other_providers` and `test_provider_plugins_have_only_required_consumer_manifests` accordingly.
    - Dependencies: Parts B and C.

16. **Sync the three catalogs and validate.**
    - Why: `AGENTS.md` requires all three catalogs list every compatible plugin and stay in sync.
    - Edits: Update the descriptions in `.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`, and `.agents/plugins/marketplace.json` to drop MCP language. Run `claude plugin validate .` from the repo root. Confirm no plugin references a path outside its own folder.
    - Dependencies: Step 15.

## Validation

### Automated Checks

- `python -m pytest tests/` from the marketplace repo root — cross-IDE matrix and adapter contract.
- `python -m pytest plugins/<plugin>/tests/` for each of the four plugins.
- BOM regression case in every gate hook test: `b"\xef\xbb\xbf" + json` with health forced `online` must produce a `deny`.
- `claude plugin validate .` from the repo root.
- `git grep -n "mcp" plugins/codex-as-advisor-guardrail plugins/codex-as-critic-guardrail plugins/claude-as-advisor-guardrail plugins/claude-as-critic-guardrail` returns nothing but incidental prose.

### Manual Checks

1. Install the marketplace in Cursor on Windows. Confirm **no** MCP server UI appears for any of the four plugins.
2. Start a fresh Cursor session in a scratch project. Confirm the `sessionStart` protocol block is injected and a presence/health line appears.
3. Attempt an edit before consulting. Confirm the write is **denied** with the shell-command instruction — this is the specific behavior the BOM bug was suppressing.
4. Run the consult command with a five-field payload. Confirm advice returns, then confirm the next edit is allowed.
5. Force an offline condition (bad model in `harness/<plugin>/config.json`). Confirm the gate disarms with an offline message rather than blocking work.
6. Repeat 2-5 in Claude Code for `codex-as-*`, and in Codex for `claude-as-*` (gate step conditional on the Step 12 spike result).

### Acceptance Criteria

- No `.mcp.json`, `mcp.json`, or `mcp/` directory exists in any of the four plugin folders, and no manifest in them contains an `mcpServers` key.
- A BOM-prefixed `preToolUse` payload produces a `deny` decision, proven by an automated test in every affected plugin.
- No hook writes a BOM to stdout — the decision JSON parses cleanly on the Cursor side.
- Every gate still fails **open** on an unparseable payload, and now prints the exception type and raw-payload prefix to stderr when it does.
- All four plugins consult their backend through a shell CLI on every host they claim to support, and the `README.md` of each states plainly which hosts have an enforcing gate and which do not.
- The three marketplace catalogs agree, and `claude plugin validate .` passes.
- No plugin references a file outside its own folder.

## Risk Mitigation

- Risk: Removing MCP from the Cursor host of `claude-as-*` removes the tool-call affordance, and the agent may simply not run the shell consult from protocol text alone.
  Mitigation: The deny message itself carries the exact command, so the agent is told what to do at the moment it is blocked, not only at session start. `codex-as-*` already relies on this shape. Accepted risk, and the first Cursor trial is the test — this is precisely what the trial is for.

- Risk: The BOM fix arms gates that have effectively been disabled on Windows, so guardrails will start denying writes that previously sailed through. This will feel like a regression.
  Mitigation: Land Part A first and trial it alone before touching transports, so a surprise denial is unambiguously attributable to the BOM fix rather than to the MCP removal. Health `pending`/`offline` states already fail open, limiting blast radius to genuinely healthy sessions.

- Risk: `afterShellExecution` may not carry `exit_code`, so a *failed* consult could unlock the gate.
  Mitigation: Keep the layered fallback in `_is_cli_consult` and add a stderr line naming which branch decided the unlock, so the trial produces evidence for Question 2 instead of a shrug. Tighten once the real payload shape is observed.

- Risk: Codex may have no pre-write hook mechanism at all, leaving `claude-as-*` unenforceable on that host after MCP is removed.
  Mitigation: Step 12 is a dedicated spike that runs *before* the deletion in Step 13, so the answer is known before the fallback is removed. If the answer is no, ship the host honestly labeled as consult-capable but gate-less rather than implying enforcement.

- Risk: `claude-as-*` gains roughly a thousand lines of ported code across two plugins, with no existing tests to catch a bad port.
  Mitigation: Port `lib/` before rewriting hooks, and bring across `codex-as-advisor-guardrail/tests/test_hooks.py` as the template for the new test files in the same step, not after.

- Risk: Committed `__pycache__/*.pyc` files are tracked and will linger after `mcp/` is deleted, leaving importable stale modules in an installed copy.
  Mitigation: Check `git ls-files` for `.pyc` entries during Step 6 and remove them plus a `.gitignore` rule as part of that step.

## Phase Split

CER is 7/8/6 — above single-unit threshold on all three axes. Run `rails-planning-phaser` on this plan before execution. The natural seams are already marked: **Part A** (BOM fix, repo-wide, independently shippable and independently trialable), **Part B** (`codex-as-*` MCP removal, small because the CLI transport already exists), **Part C** (`claude-as-*` full port — by far the largest, and itself splittable at Step 12's spike boundary), and **Part D** (repository reconciliation). Part A alone is enough to trial in Cursor today.

## Evidence / References

- Forum thread: `https://forum.cursor.com/t/hooks-not-firing-cannot-have-guardrails/168407/6` — reply from `deanrie` (Cursor) confirming the Windows stdin UTF-8 BOM prefix, recommending `readFileSync(0, "utf8").replace(/^﻿/, "")` before `JSON.parse`, noting it applies to hooks imported from `~/.claude`, and stating it is a tracked issue with no ETA.
- Defect site: `plugins/codex-as-advisor-guardrail/hooks/advisor_gate.py:51-56`; helper at `hooks/advisor_streams.py:29-38`.
- MCP-coupled gate: `plugins/claude-as-advisor-guardrail/hooks/advisor_gate.py` (`has_live_server`), backed by `hooks/advisor_markers.py`.
- Reference architecture: `plugins/codex-as-advisor-guardrail/docs/architecture.md`, `docs/hosts/cursor.md` (records the existing "deliberately avoids MCP" decision), `cli/consult_advisor.py`, `hooks/cursor-hooks.json`.
- Claude backend invocation to port: `plugins/claude-as-advisor-guardrail/mcp/advisor_server.py:52-63`.
- Tests that break by construction: `tests/test_cross_ide_guardrails.py:62-66`; `plugins/{codex,cursor}-as-*/tests/test_{advisor,critic}_server.py`.
- Repository hard rules: `AGENTS.md` — no cross-folder references, no `version` in `.claude-plugin/plugin.json`, all three catalogs in sync, `claude plugin validate .` before commit.
- Unverified at plan time: the Cursor `afterShellExecution` payload shape, Codex hook support, and whether Cursor agents reliably follow shell-consult protocol text without an MCP tool affordance. All three are recorded as open questions.

## Complaints / Friction

### The guardrails reported healthy while enforcing nothing

**What happened:** Every Cursor write gate in this marketplace has been fail-open on Windows since it shipped, because a BOM broke `json.load` and the defensive handler exits 0 to allow the write.

**Why this made the task harder:** There was no signal. Hooks fired, the session-start protocol block appeared, health probes ran — every observable indicator said the guardrail was working. The failure was only visible from the outside, as "deny rules never apply", which reads like a Cursor bug rather than an encoding bug in our own parse path.

**What was tried:** Escalated to the Cursor forum, which produced the actual root cause from a Cursor engineer.

**What would improve this:** A gate that fails open should say why, every time, on stderr — Step 4 of this plan. Beyond that, the guardrails have no self-test: nothing in the test suite fed a realistic host payload to a gate and asserted a denial, which is why five plugins shared one defect undetected.

**What I think:** The fail-open design is right and should stay. The defect was not fail-open; it was *silent* fail-open. The BOM regression test in Step 5 is the durable fix — the encoding change alone would leave the next transport bug just as invisible.
