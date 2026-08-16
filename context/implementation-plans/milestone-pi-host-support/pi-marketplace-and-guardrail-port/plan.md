# Plan: Make the Agentic Rails Marketplace Installable by Pi and Port Seven Guardrails

## Metadata

- Task Type: `FEATURE`
- Status: `Draft`
- Owner: `Jarryd Adaens`
- Last Updated: `16 August 2026`

## Linked Context

- Milestone: `context/implementation-plans/milestone-pi-host-support/` (no `context/milestones/` document exists in this repository; the milestone is defined by this folder, matching the two existing milestones)
- Story: none recorded separately; this plan is the story of record
- Spike output: `context/pi-agentic-ide/pi-agentic-ide.md` — **read this first.** It is the verified reference for pi 0.84.2 and the source of every mechanism this plan relies on.
- Design source: `context/design.md` §4 (repository layout) and §5 (plugin granularity), both of which this plan amends
- Related Plans:
  - `context/implementation-plans/milestone-per-ide-marketplace/split-plugins-by-host/plan.md` — established the per-host root layout this plan extends with a fourth, structurally different root
  - `context/implementation-plans/milestone-cursor-guardrail-parity/remove-mcp-and-fix-cursor-bom/plan.md` — the MCP-removal direction this plan inherits; pi has no MCP at all
- Source guardrails being ported: `plugins/cursor/python-uv-guardrail/`, `plugins/cursor/readme-name-guardrail/`, `plugins/cursor/claude-as-advisor-guardrail/`, `plugins/cursor/codex-as-advisor-guardrail/`, `plugins/cursor/cursor-as-advisor-guardrail/`, `plugins/cursor/claude-as-critic-guardrail/`
- External Tooling: `rails-planning-phaser` (**run before execution** — see Phase Split)

## CER

- Complexity: `7`
- Effort: `8`
- Risk: `6`
- Notes: Hand-graded. Complexity is driven by a new host with a genuinely different distribution model (no manifests, no catalog, in-process TypeScript) plus one reentrancy-sensitive component (the review bot). Effort is breadth: seven guardrails, a shared library, a new test harness in a language the repository does not currently test in, and edits to three repository-level documents. Risk is concentrated in three places — a guardrail that misfires against an error-prone local model produces a retry loop rather than a clean failure (proven, Evidence 9.2); pi's `tool_call` fails **closed**, inverting this repository's standing discipline so an unwrapped handler wedges the guarded tool (Evidence 9.5); and this is the first change to touch the repository root that the other three hosts also consume. **All three axes exceed the single-unit threshold; this plan is expected to be fractured before execution.**
- Revision, 16 August 2026: every open question except the `git-push` escape-hatch policy was resolved by follow-up investigation. Two answers changed the design rather than merely confirming it — see Evidence 9.5 and 9.6, and the corrected guidance in Execution Steps 2, 6, and 7.

## Objective

Make the `agentic_rails_marketplace` repository installable by the Pi coding agent as a single pi package, and deliver seven guardrails inside it: three deterministic blockers (bare-Python invocation, non-root `readme.md`, `git push`), three cross-vendor advisor guardrails that reach Codex, Cursor, and Claude through pi's native custom-tool API rather than MCP, and one wrap-up review bot that has an external Opus session approve or reject the session's changes and returns bounded remediation to a 131k-context local model.

## Scope

### In Scope

- A single repository-root `package.json` declaring the pi package and globbing the pi extension sources. **Decided:** one repo-root package, not per-guardrail packages (see Questions Q1 for the reasoning and what was given up).
- A `plugins/pi/` source root holding one folder per guardrail, each with `extensions/<name>.ts`, a `README.md`, and its own tests.
- A `plugins/pi/shared/` module carrying logic more than one guardrail needs: shell-command segmentation, harness-config loading, Windows CLI resolution, subprocess running with a timeout, and output capping.
- The seven guardrails listed in the Objective, each reading its optional per-project config from the existing `harness/<guardrail-name>/config.json` seam.
- A pi-specific structural test module, plus an exclusion of `plugins/pi/` from the existing host-matrix tests in `tests/test_cross_ide_guardrails.py`, which hard-code three hosts and require a host manifest per plugin folder.
- Behavioral tests for every deny decision, including the explicit case that a deny message's own recommended remedy is not itself denied.
- Amendments to `context/design.md` §4 and §5, `AGENTS.md`, and `README.md`, landed **after** the behavior they describe.

### Out Of Scope

- Any behavioral change to the Claude Code, Codex, or Cursor copies of these guardrails. The pi guardrails are new siblings, not a refactor of the existing ones.
- Publishing anything to npm. Distribution is git and local path only.
- Porting `jobs-done-guardrail`, `local-advisor-guardrail`, or any critic (as opposed to advisor) guardrail to pi.
- A pi host for `codex-as-critic-guardrail` / `cursor-as-critic-guardrail` / `claude-as-critic-guardrail`. The user asked for *advisors* plus one review bot; the critic personas are a separate decision.
- Pi's SDK, RPC, and JSON event-stream surfaces.
- Fixing the pre-existing tension between the repository's own nested `README.md` files and the `readme-name-guardrail` rule (see Complaints / Friction).

## Non-Goals

- **Do not build a pi marketplace catalog.** Pi has no such concept — verified, see Evidence 9.5. There is no `marketplace.json` analog, no `marketplace add`, and no per-repository registry. Any work that invents one is wasted.
- **Do not achieve per-guardrail install/remove on pi.** A git source clones from the repository root with no subdirectory selector, so per-guardrail git install is structurally impossible without one repository per guardrail. Granularity is delivered by `pi config` filtering instead. This is a deliberate, recorded departure from `context/design.md` §5.
- **Do not port the hook plumbing.** Stdin decoding, BOM stripping, JSON response envelopes, marker files, and `uv`-mediated Python launching are all artifacts of a subprocess hook transport pi does not have. Port the *decisions*, delete the *transport*.
- Do not make the pi extensions share code with the PowerShell or Python implementations. They are independent reimplementations of the same rules.

## Current Understanding

### What pi is, in the two sentences that matter here

Pi (`@earendil-works/pi-coding-agent`, v0.84.2, installed at `C:\Users\Jarry\AppData\Local\pi-node\current\`) extends through **TypeScript extensions loaded in-process**, registered via `pi.on(event, handler)` and `pi.registerTool(def)`. It distributes through **packages** — npm-shaped folders declaring resources under a `pi` key in `package.json`, installable from npm, git, or a local path.

Full mechanism reference lives in `context/pi-agentic-ide/pi-agentic-ide.md`; it is not repeated here.

### The four pi mechanisms this plan is built on

| Mechanism | Used by |
| --- | --- |
| `tool_call` returning `{ block, reason, terminate? }` | python-uv, readme-name, git-push, and the advisor write gates |
| `pi.registerTool()` | the three advisor guardrails — this is the MCP replacement |
| `agent_settled` | the review bot; it is the only event meaning "pi will not continue on its own" |
| `package.json` `pi.extensions` globs + settings filtering | the whole distribution model |

### Where things will live

```text
agentic_rails_marketplace/
├── package.json                       # NEW — the one pi package manifest for the repo
└── plugins/
    └── pi/                            # NEW root; structurally unlike the other three
        ├── shared/                    # not matched by the extension glob; imported
        │   ├── bash-segments.ts
        │   ├── harness-config.ts
        │   ├── cli-resolution.ts
        │   ├── run-external.ts
        │   └── budget.ts
        ├── python-uv-guardrail/
        │   ├── extensions/python-uv-guardrail.ts
        │   ├── tests/
        │   └── README.md
        ├── readme-name-guardrail/
        ├── git-push-guardrail/
        ├── codex-as-advisor-guardrail/
        ├── cursor-as-advisor-guardrail/
        ├── claude-as-advisor-guardrail/
        └── claude-as-review-bot-guardrail/
```

Root manifest, in the shape verified against the shipped `docs/packages.md`:

```json
{
  "name": "agentic-rails-pi",
  "private": true,
  "keywords": ["pi-package"],
  "pi": { "extensions": ["plugins/pi/*/extensions/*.ts"] },
  "peerDependencies": {
    "@earendil-works/pi-coding-agent": "*",
    "typebox": "*"
  }
}
```

The glob deliberately matches only `<guardrail>/extensions/*.ts`, which is why
`plugins/pi/shared/` is importable without being loaded as an extension. `private: true`
because nothing is published to npm; `peerDependencies` with `"*"` because pi bundles its
own core packages and forbids bundling them.

### Existing behaviors that must be preserved

- **The harness seam.** Every guardrail reads `harness/<guardrail-name>/config.json` from the project root, treats absent/empty/malformed as "enforce with defaults", and honors `"enabled": false`. Same file the Cursor and Claude hosts use, so a project never grows a second config location for one guardrail.
- **Fail open — and on pi you have to write it yourself.** An internal guardrail error must never block the tool it guards. The other hosts get this from `exit 0`. Pi does the **opposite** by default: `docs/extensions.md` states that "`tool_call` errors block the tool (fail-safe)", so an unhandled throw wedges the guarded tool for the session. Every `tool_call` handler body must be wrapped in `try/catch` returning `undefined`, and each guardrail needs a test that induces an internal error and asserts the tool is allowed through.
- **Deny-message fidelity.** The python-uv deny text names the offender and lists the `uv` remedies; the readme deny text suggests `<parent-slug>-readme.md`. Reproduce the wording, since the model acts on it.

### The decision logic being ported

- **python-uv** (`plugins/cursor/python-uv-guardrail/hooks/enforce-uv-python.ps1`): split the command on `||`, `&&`, `;`, `|`, `&`, newlines, and parentheses; per segment, skip inline `VAR=value` assignments and the wrappers `sudo`, `env`, `time`, `nice`, `command`, `exec`, `builtin`, `\`; take the leading executable; strip directory and `.exe`; exempt segments led by `uv`/`uvx`; block on `^(py|python(\d+(\.\d+)?)?|pip\d*)$`. Config keys: `enabled`, `blockedPattern`, `allowCommands`.
- **readme-name** (`plugins/cursor/readme-name-guardrail/hooks/readme-guard-common.ps1` and its two callers): a path is forbidden when its leaf is exactly `readme.md` (any casing) and its parent is not the project root. Config keys: `enabled`, `allowPaths` (regexes against the repo-relative POSIX path). Two enforcement points — the `write`/`edit` path check, and a `bash` check for `git add` / `git commit` staging one.
- **advisors**: Claude runs `claude -p --model opus --effort high --permission-mode plan --tools Read,Grep,Glob --safe-mode --no-session-persistence --output-format text`. Codex runs `codex exec` with `model` defaulting to `gpt-5.6-sol` and `effort` to `high`. Cursor runs `agent --print --mode ask --trust` with model `cursor-grok-4.6-high`, prompt over UTF-8 stdin, OS sandbox explicitly disabled on Windows. Exact Codex flag spelling is a discovery step (Q3).

### Constraints

- **131,072-token context, `qwen3.8-27b-q4km`.** Every byte a guardrail injects is a byte the operator does not get. Advisor replies and review output are capped, not merely "kept short".
- **Local models thrash on false positives.** Proven: a bad pattern cost six wasted tool calls (Evidence 9.2).
- **Windows.** The repository targets Windows; pi ships its own Node (v22.23.2), and `.cmd` shims require `cmd.exe /c` when spawned without a shell.
- **Erasable TypeScript only.** Source must avoid enums and namespaces, use explicit `.ts` extensions on relative imports, and use `import type` for type-only imports — otherwise it runs under pi's jiti loader but cannot be tested by Node. Pi's own examples already follow this style.
- **`user_bash` is the human.** No guardrail may hook it.
- **`tool_call` fails closed.** See the fail-open bullet above; this is the one place pi's defaults actively contradict the repository's convention.

## Questions / Unknowns

- Q: One repo-root package, or one package per guardrail?
  Impact: Determines whether install granularity is install/remove or enable/disable, and whether the repository root is touched at all.
  Status: `ANSWERED`
  Answer: **One repo-root package.** Chosen by the user on 16 August 2026. Per-guardrail packages would have restricted installs to local paths only, because a git source has no subdirectory selector. The cost is that `context/design.md` §5's "a plugin is the unit of independent install-and-remove" does not hold on pi; granularity moves to `pi config` filtering. That amendment is an explicit deliverable, not an oversight.

- Q: How are TypeScript extensions tested in a repository whose test suite is Python and one `.mjs` file?
  Impact: Blocks the behavioral half of validation. Determines whether a dev dependency lands at the repository root.
  Status: `ANSWERED` — verified 16 August 2026.
  Answer: **Pi's bundled Node is v22.23.2 and runs `.ts` directly**; type stripping is on by default. `node.exe --test "**/*.test.ts"` runs `node:test` suites — quote the glob, because `--test <directory>` fails (the default test-file glob does not match `.ts`). **No dev dependency, no build step, no `vitest`.** Three constraints, all verified by failure: enums and namespaces throw `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` (they need transformation, not erasure); relative imports need an explicit `.ts` extension or throw `ERR_MODULE_NOT_FOUND`; type-only imports must use `import type`. None of this bites, because **pi's own shipped examples already use exactly that style** (`examples/extensions/plan-mode/index.ts`, `subagent/index.ts`, `doom-overlay/index.ts`), so one source style satisfies both pi's jiti loader and Node's stripper.

- Q: What is the exact Codex CLI invocation for model and reasoning effort?
  Impact: The codex advisor cannot be written without it.
  Status: `ANSWERED` — read from `plugins/cursor/codex-as-advisor-guardrail/lib/advisor_consult.py:110-127`.
  Answer: `codex exec --ephemeral --skip-git-repo-check --sandbox read-only --model <model> -c model_reasoning_effort="<effort>" -` with the prompt on stdin (the trailing `-`). Defaults are `gpt-5.6-sol` / `high`; valid efforts are `minimal`, `low`, `medium`, `high`, `xhigh`. When `fast` is set, `-c service_tier="fast"` is appended before the `-`. Note `--sandbox read-only` is what enforces the read-only advisor contract, and `--ephemeral` is what keeps the consult out of Codex's session history — both must be carried over.

- Q: Does an unhandled error inside a pi extension handler kill the session or is it isolated?
  Impact: Determines how much defensive wrapping the fail-open discipline actually requires.
  Status: `ANSWERED` — `docs/extensions.md` §Error Handling.
  Answer: **Pi fails CLOSED where Agentic Rails fails open, and this inverts a standing rule.** Verbatim: "Extension errors are logged, agent continues" but "**`tool_call` errors block the tool (fail-safe)**". Every PowerShell and Python guardrail in this repository exits 0 on an internal error precisely so a hook bug can never block the tool it guards; on pi an unhandled throw in a `tool_call` handler blocks the call, so a typo wedges `bash` for the whole session. Wrapping every `tool_call` handler body in `try/catch` and returning `undefined` is therefore **mandatory**, and its absence is a defect rather than a style nit. (Tool `execute` errors behave differently and correctly: throw, and pi reports it to the LLM with `isError: true` and continues.)

- Q: Is `agent_settled` reentrant, and how does pi behave when a handler calls `pi.sendUserMessage` from inside it?
  Impact: The review bot's loop guard depends on this. A naive implementation could loop until the context window fills.
  Status: `ANSWERED` — measured live in RPC mode, 16 August 2026. **The answer invalidates two of the three guards this plan originally proposed.**
  Answer: **It is reentrant.** A probe that injected a message from `agent_settled` produced three full agent runs and stopped only because a hard counter stopped it. Both intuitive guards are **provably useless**: `inFlight` read `false` on every reentrant fire, because `sendUserMessage` resolves as soon as the message is queued — long before the run it triggers completes — so the flag clears before the next `agent_settled` arrives; and `ctx.isIdle()` read `true` on every fire, including the reentrant ones. **Only the hard cycle counter works.** A diff fingerprint remains useful for the unchanged-tree case but stops nothing when the agent edits files each cycle, since the fingerprint differs every time. Separately: under `pi -p` the mechanism does not work at all — one `agent_settled`, the injected message never runs, and the deferred call throws "This extension ctx is stale after session replacement or reload." A wrap-up guardrail must check `ctx.mode` and stand down in `"print"`.

- Q: How large is a git install of this repository, given it carries three host trees pi has no use for?
  Impact: Install-time cost and whether a slimmer distribution repository is warranted later.
  Status: `ANSWERED` — measured.
  Answer: 6.0 MB working tree, 2.1 MB of git objects, 376 tracked files, no cache directories tracked. A git install costs roughly 8 MB. Not worth optimizing; drop the idea of a slimmer distribution repository.

- Q: Should `git-push-guardrail` have any escape hatch at all?
  Impact: The user's stated intent is enforcement against an error-prone local model.
  Status: `ANSWERED` — decided 17 August 2026 and shipped in Phase 2.
  Answer: An `enabled` flag for parity with its siblings and **no** per-command allowlist. `enabled: false` is a deliberate, visible, project-level act; a regex allowlist on a hard prohibition is an accident waiting to happen. The guardrail also does not hook `user_bash`, so the human can still push by hand — which is the point.

- Q: Does the pi `readme-name-guardrail` match its Cursor sibling exactly on `git commit <path>`?
  Impact: Cross-tree behavioral parity, which the repository otherwise treats as an invariant.
  Status: `ANSWERED` — divergence found during Phase 2 and deliberately kept.
  Answer: **No, and the pi copy is stricter on purpose.** `Get-CommitOffenders` in the Cursor host's `block-readme-git.ps1` inspects only *staged* files (`git diff --cached`) plus `git ls-files -m` under `-a`, so an explicit path argument such as `git commit docs/readme.md` on an unstaged or untracked file passes through it. The pi copy also treats explicit non-flag path arguments as candidates, so it blocks regardless of index state. This is the one place the pi guardrail is knowingly stricter than its sibling. It is recorded here rather than "fixed" in either direction, because bringing the Cursor host into line is a change to a shipped guardrail and belongs to its own story.

## Execution Steps

1. **Stand up the package skeleton and the shared module.**
   - Why: Nothing can be tested or installed until pi can find an extension in this repository.
   - Edits: Create the repo-root `package.json` shown above. Create `plugins/pi/shared/` with `bash-segments.ts` (segmentation, wrapper skipping, leading-executable resolution, basename normalization), `harness-config.ts` (load `harness/<name>/config.json`, absent/empty/malformed → defaults, honor `enabled`), and `budget.ts` (deterministic character capping with a truncation marker).
   - Dependencies: none.

2. **Stand up the test harness.**
   - Why: Writing six more guardrails before knowing how they are tested guarantees rework. Q2 is answered, so this is now execution rather than investigation.
   - Edits: Behavioral tests run as `node.exe --test "plugins/pi/**/*.test.ts"` using pi's own bundled Node at `C:\Users\Jarry\AppData\Local\pi-node\current\node.exe` — no dev dependency, no build step. Quote the glob; `--test <directory>` does not match `.ts`. All source must stay within erasable syntax (**no enums, no namespaces**), use explicit `.ts` extensions on relative imports, and use `import type` for type-only imports. Add `tests/test_pi_package.py` (structural: the root glob resolves to real files; every `plugins/pi/*/` folder has `extensions/` and a `README.md`; no `.claude-plugin`/`.codex-plugin`/`.cursor-plugin` directory appears anywhere under `plugins/pi/`; `plugins/pi/shared/` is not matched by the extension glob) and add a lint-style assertion there that no `.ts` file under `plugins/pi/` contains `enum ` or `namespace `, since that failure is otherwise only discovered at runtime.
   - Dependencies: step 1.

3. **Port `python-uv-guardrail`.**
   - Why: It is the guardrail whose logic is most load-bearing and the one the spike proved is easiest to get subtly wrong.
   - Edits: `plugins/pi/python-uv-guardrail/extensions/python-uv-guardrail.ts` — `tool_call` on `bash`, delegating to the shared segmentation, blocking **without** `terminate` because a legitimate remedy exists. Behavioral tests must include `uv run python --version`, `uvx ruff`, `sudo python x.py`, `FOO=1 python x.py`, `cat x | python`, `/usr/bin/python3.12 x.py`, `C:\Python314\python.exe x.py`, and a plain `uv --version`.
   - Dependencies: steps 1–2.

4. **Port `readme-name-guardrail`.**
   - Why: Second pure-logic port; shares the path handling the git check also needs.
   - Edits: `plugins/pi/readme-name-guardrail/extensions/readme-name-guardrail.ts` — `tool_call` on `write`/`edit` for the path rule, and on `bash` for `git add` / `git commit` staging a forbidden path. Reproduce the `<parent-slug>-readme.md` suggestion.
   - Dependencies: steps 1–2.

5. **Write `git-push-guardrail`.**
   - Why: New guardrail with no existing sibling to port from; small and self-contained.
   - Edits: `plugins/pi/git-push-guardrail/extensions/git-push-guardrail.ts` — `tool_call` on `bash`, segment-aware so `x && git push` is caught, matching `git` as the leading executable of a segment whose arguments contain `push` (covering `git -C <dir> push`, `git push --force`, `git push -u origin main`). Return `terminate: true`: there is no remedy the agent may reach, and terminating is what stopped the retry loop in Evidence 9.3. Must **not** hook `user_bash`.
   - Dependencies: steps 1–2.

6. **Build the advisor runner, then the three advisor guardrails.**
   - Why: The three differ only in which CLI they spawn and what persona they carry; building the runner once is the DRY path.
   - Edits: `plugins/pi/shared/cli-resolution.ts` (locate `claude`, `codex`, and Cursor's `agent` on Windows without operator PATH changes, reproducing the search paths in `plugins/cursor/codex-as-advisor-guardrail/lib/windows_runtime.py`, and wrapping `.cmd`/`.bat` in `cmd.exe /c`) and `plugins/pi/shared/run-external.ts` (spawn with UTF-8 stdin, a configurable timeout, and `ctx.signal` wired through so Esc cancels). Then one extension per advisor, each registering a single tool — `consult_codex_advisor`, `consult_cursor_advisor`, `consult_claude_advisor` — with a deliberately short `promptSnippet`, and each holding session-scoped in-memory state for a `tool_call` write gate on `write`/`edit` that lifts after the first successful consult. Cap every advisor reply before it reaches the model.
   - The three command lines, all verified:
     - Claude — `claude -p --model opus --effort high --permission-mode plan --tools Read,Grep,Glob --safe-mode --no-session-persistence --output-format text`
     - Codex — `codex exec --ephemeral --skip-git-repo-check --sandbox read-only --model gpt-5.6-sol -c model_reasoning_effort="high" -` (prompt on stdin via the trailing `-`; `--sandbox read-only` is what enforces the read-only contract and `--ephemeral` keeps the consult out of Codex's history — carry both)
     - Cursor — `agent --print --mode ask --trust --model cursor-grok-4.6-high`, prompt over UTF-8 stdin, OS sandbox explicitly disabled on Windows, and never `--force`/`--yolo`/`--auto-review`
   - Dependencies: steps 1–2.

7. **Build `claude-as-review-bot-guardrail`.**
   - Why: The highest-risk component, and the one whose failure mode is a context-burning loop rather than a clean error. It goes last so the shared runner is already proven.
   - Edits: `plugins/pi/claude-as-review-bot-guardrail/extensions/claude-as-review-bot-guardrail.ts` — on `agent_settled`: **return immediately when `ctx.mode === "print"`** (the mechanism does not work there at all — Evidence 9.7); skip when the cwd is not a git repository or has no changes; enforce a **hard per-session cycle counter as the primary guard**; fingerprint `git status --porcelain` plus the diff as a secondary guard for the unchanged-tree case only; build a bounded review input (changed-file list plus a byte-capped diff); spawn the Claude CLI with the Objective's flag set, asking for a small fixed shape — one-word verdict, then at most three issues, each one line of problem plus one line of fix; cap the whole reply hard before use. On `REJECT`, feed it back with `pi.sendUserMessage`. On `APPROVE`, `ctx.ui.notify` only and spend no context. Config: `enabled`, `maxCycles`, `diffBudgetBytes`, `reviewBudgetChars`, `timeoutSeconds`.
   - **Do not implement an in-flight boolean or an `ctx.isIdle()` check as a loop guard.** Both were measured returning the non-blocking value on every reentrant fire (Evidence 9.6). Writing them costs nothing and buys nothing, and their presence makes the counter look like a backstop when it is in fact the only thing working.
   - Dependencies: steps 1–2, 6.

8. **Integrate with the existing test suite.**
   - Why: `tests/test_cross_ide_guardrails.py` hard-codes `HOSTS = ("claude", "codex", "cursor")` and asserts every plugin folder carries exactly one host manifest. `plugins/pi/` violates that by construction.
   - Edits: Exclude `plugins/pi/` from the host-matrix assertions with a comment stating *why* pi is structurally different, so a later reader does not "fix" the omission. Confirm `claude plugin validate .` still passes with a root `package.json` present.
   - Dependencies: steps 3–7.

9. **Install end to end and exercise every guardrail against the real local model.**
   - Why: Structural tests prove shape; only a live run proves a guardrail survives contact with `qwen3.8-27b-q4km`.
   - Edits: none — this is validation. See Validation → Manual Checks.
   - Dependencies: step 8.

10. **Update the documentation, last.**
    - Why: House rule — documentation follows landed behavior.
    - Edits: `context/design.md` §4 (add the pi root and state plainly that it is *not* a fourth peer: no manifest, no catalog, one package at the repository root) and §5 (record the granularity departure, why it was forced, and what would have to change in pi to reverse it). `AGENTS.md` layout and conventions sections. `README.md` — add the pi guardrails to the plugin table and add a pi install section, which is `pi install` rather than `/plugin marketplace add`.
    - Dependencies: step 9.

## Validation

### Automated Checks

- `python -m pytest tests/` from the repository root — the existing suite plus the new `tests/test_pi_package.py`.
- `"C:\Users\Jarry\AppData\Local\pi-node\current\node.exe" --test "plugins/pi/**/*.test.ts"` — every deny decision in `plugins/pi/shared/`, plus one induced-internal-error case per guardrail asserting the guarded tool is **allowed** through.
- `claude plugin validate .` from the repository root — must still pass with a root `package.json` present.
- `python scripts/rails_lint.py .` does **not** apply here; that is the tooling repository's gate, not this one.

### Manual Checks

1. `pi install "D:/Code Projects/agentic_rails/agentic_rails_marketplace"` from a clean `~/.pi/agent/settings.json`; confirm `pi list` shows it and `pi config` lists all seven extensions individually.
2. Ask pi to run `python --version`; confirm one block with the ported message. Then ask it to run `uv run python --version`; confirm it is **allowed**. This is the Evidence 9.2 regression and is the single most important manual check in this plan.
3. Ask pi to create `docs/readme.md`; confirm the block and the `docs-readme.md` suggestion. Confirm a root `README.md` is still allowed.
4. Ask pi to `git push`; confirm a single block and that the agent stops rather than retrying.
5. With one advisor installed, confirm the first `write` is denied, the advisor tool is offered and callable, and the write is allowed after a successful consult. Confirm the reply is capped.
5b. **The codex advisor cannot be live-tested as of 17 August 2026 — the Codex quota is exhausted.** Build and unit-test it against the verified command line, then verify only that an unreachable/failing backend **disarms the gate** rather than wedging the session, which is the failure path that matters and is testable without quota. Its consult path stays unverified until quota returns; say so plainly rather than implying it was checked.
6. Finish a real change and let the session settle; confirm the review bot fires exactly once, that an `APPROVE` costs no context, that a `REJECT` returns something a person would call helpful in under ~2,000 characters, and that it does not fire again on an unchanged tree.
6b. Force the loop: set `maxCycles` to 2 and give the agent work that keeps changing files each cycle, so the fingerprint differs every time. Confirm the counter alone stops it at 2. This is the case the fingerprint cannot catch, and it is the one that matters.
6c. Run the same session under `pi -p` and confirm the review bot stands down silently rather than erroring on a stale ctx.
7. Disable one guardrail via `pi config`; confirm the other six still load.
8. Drop `harness/python-uv-guardrail/config.json` with `{"enabled": false}` into a test project; confirm the guardrail stands down there and nowhere else.
9. `pi remove <path>`; confirm `settings.json` returns to its prior state.

### Acceptance Criteria

- One `pi install` makes all seven guardrails available; `pi config` toggles each independently.
- Every deny decision reproduces its Cursor-host sibling's outcome on the shared test cases, and no deny message recommends a remedy that the same guardrail blocks.
- `git push` is blocked with `terminate: true` and the agent does not retry.
- Each advisor exposes exactly one registered tool, gates the session's first write until consulted, and returns a capped reply. No MCP anywhere.
- The review bot fires at most `maxCycles` times per session, never on an unchanged fingerprint, and never emits more than `reviewBudgetChars` into the session.
- An induced internal error in any guardrail allows the guarded tool through rather than blocking it.
- The existing Claude, Codex, and Cursor trees are byte-identical apart from the documented catalog/README additions.
- `context/design.md`, `AGENTS.md`, and `README.md` describe the pi root accurately, including its deliberate structural difference.

## Risk Mitigation

- Risk: A guardrail false positive sends the local model into a retry loop, burning context and time. **Proven, not theoretical** (Evidence 9.2 — six wasted tool calls).
  Mitigation: Port the segment-aware logic rather than a regex; make "the recommended remedy is not itself blocked" an explicit test case per guardrail; use `terminate: true` only where no remedy exists.

- Risk: The review bot loops — `agent_settled` → inject message → agent runs → settles → injects again. **Confirmed live: three full runs, stopped only by a hard counter.**
  Mitigation: A hard per-session cycle counter is the primary and only load-bearing guard. Do **not** rely on an in-flight boolean or `ctx.isIdle()` — both were measured returning the non-blocking value on every reentrant fire (Evidence 9.6). A diff fingerprint is kept as a secondary guard for the unchanged-tree case only, and is explicitly not trusted to stop a loop where the agent edits files each cycle.

- Risk: A bug in a pi guardrail wedges the tool it guards for the whole session, because pi's `tool_call` fails **closed** — the inverse of every other host in this repository.
  Mitigation: Every `tool_call` handler body is wrapped in `try/catch` returning `undefined`. Add a test per guardrail that induces an internal error and asserts the tool is allowed through. This is the one place where pi's defaults actively fight the repository's convention, so it gets a test rather than a comment.

- Risk: A root `package.json` changes how the other three hosts see this repository, or how `claude plugin validate` behaves.
  Mitigation: Validate before and after in the same session; land the root manifest alone in Phase 1 so a regression is attributable to one commit.

- Risk: The advisor and review-bot subprocesses hang, freezing the session.
  Mitigation: Every external call carries an explicit timeout and `ctx.signal`, and a timeout is reported to the model as a plain failure, never as a block.

- Risk: Shared code in `plugins/pi/shared/` couples guardrails that the operator believes are independent — disabling one extension does not remove the shared module.
  Mitigation: Accepted, and a direct consequence of the single-package decision. Keep `shared/` to pure, side-effect-free functions plus one subprocess runner, so a fault there is testable in isolation rather than emergent.

- Risk: Cross-tree drift — a rule fixed in the pi copy and not in the Cursor and Claude copies, or vice versa.
  Mitigation: Accepted; it is the same trade-off the per-host split already made. Reduce it by keeping the shared test *cases* (not the code) aligned across hosts.

- Risk: `pi install` with a local path writes a **relative** path into `settings.json` (Evidence 9.4), so a documented command may resolve elsewhere on another machine.
  Mitigation: Document the git source as the supported install and the local path as a development convenience only, with the relative-path behavior stated explicitly.

- Risk: Windows CLI resolution for `claude`, `codex`, and `agent` fails under pi's bundled Node.
  Mitigation: Reproduce the already-hardened search paths from `windows_runtime.py`; on failure the advisor reports itself offline and its write gate **disarms**, matching the Codex host's existing behavior — an unreachable advisor must not wedge the session.

## Phase Split

All three CER axes exceed the single-unit threshold, so this plan should be fractured before execution. **Run `rails-planning-phaser` against this file.** The natural seams, offered as input to that skill rather than as a finished split:

| Phase | Content | Rough CER |
| --- | --- | --- |
| 1 | Root `package.json`, `plugins/pi/shared/` foundations, test harness (Q2), `python-uv-guardrail` | C5 E5 R4 |
| 2 | `readme-name-guardrail`, `git-push-guardrail` | C3 E3 R3 |
| 3 | CLI resolution, external runner, the three advisor guardrails | C6 E6 R5 |
| 4 | `claude-as-review-bot-guardrail` | C7 E5 R7 |
| 5 | Test-suite integration, live end-to-end run, documentation amendments | C3 E4 R3 |

Phases 2 and 3 are independent of each other once Phase 1 lands. Phase 4 depends on Phase 3's runner. Phase 5 depends on everything.

## Evidence / References

Verified live on 16 August 2026 against pi 0.84.2. Full detail in `context/pi-agentic-ide/pi-agentic-ide.md` §9; summarized here because these findings are what the plan is built on.

- **9.1 — `tool_call` blocking works.** A throwaway extension loaded with `pi -e` blocked a `bash` call; the model received the reason and reported the interception accurately.
- **9.2 — A naive pattern caused six wasted tool calls.** The spike regex also blocked `uv run python --version`, the remedy its own message recommended. The local model tried six variations before giving up. This is the origin of the "port the logic, not a regex" rule and of the explicit remedy-not-blocked test case.
- **9.3 — `terminate: true` stops the thrash.** A second extension blocked `git push` with `terminate: true`; the agent stopped immediately. Direct contrast with 9.2, and the basis for the differing settings in steps 3 and 5.
- **9.4 — Local-path package install/remove works**, and pi rewrites the path into `settings.json` **relative to the settings file** — a portability footgun.
- **9.5 — Pi's `tool_call` fails closed.** From `docs/extensions.md`: "Extension errors are logged, agent continues" but "`tool_call` errors block the tool (fail-safe)". Inverts this repository's fail-open discipline; makes handler wrapping mandatory.
- **9.6 — `agent_settled` is reentrant, and the obvious guards do not work.** Measured in RPC mode: injecting a message from the handler produced three full agent runs, stopped only by a hard counter. `inFlight` read `false` and `ctx.isIdle()` read `true` on every reentrant fire. Only a cycle counter is load-bearing.
- **9.7 — Print mode cannot host a wrap-up guardrail.** Under `-p` the probe saw one `agent_settled`, the injected message never ran, and the deferred call threw "This extension ctx is stale after session replacement or reload."
- **9.8 — Pi's bundled Node runs and tests TypeScript directly.** v22.23.2; `node --test "**/*.test.ts"` works. Enums and namespaces throw `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`; extensionless relative imports throw `ERR_MODULE_NOT_FOUND`. No dev dependency needed.
- **9.9 — A git install of this repository costs ~8 MB.** 6.0 MB tree, 2.1 MB objects, 376 files. Non-issue.
- **9.10 — There is no marketplace to register.** `pi list` on a fresh install reports "No packages installed"; there is no catalog file and no `marketplace add`.
- Codex advisor command line read from `plugins/cursor/codex-as-advisor-guardrail/lib/advisor_consult.py:110-127` (the `command()` function), not inferred.
- Node type-stripping constraints cross-checked against the Node 22.6.0 release notes and the `nodejs/amaro` enum/namespace issue: [nodejs.org/en/blog/release/v22.6.0](https://nodejs.org/en/blog/release/v22.6.0), [github.com/nodejs/amaro/issues/22](https://github.com/nodejs/amaro/issues/22).
- Documentation source of record: the copy shipped inside the installed package at `C:\Users\Jarry\AppData\Local\pi-node\current\node_modules\@earendil-works\pi-coding-agent\docs\`, which is version-matched and therefore preferable to `pi.dev`. `extensions.md` (2,992 lines) and `packages.md` are the two that matter.
- Working reference implementations shipped with pi: `examples/extensions/permission-gate.ts` (block a bash command), `protected-paths.ts` (block by path), `auto-commit-on-exit.ts` (teardown work), `subagent/` and `handoff.ts` (nested agents).
- Unverified claim carried into this plan: the exact Codex CLI flags for model and reasoning effort (Q3). Everything else in Current Understanding was read from source.

## Complaints / Friction

### The repository violates its own `readme-name-guardrail`

**What happened:** `AGENTS.md` requires "Every plugin folder has a `README.md`", and 20-odd plugin folders comply. The `readme-name-guardrail` this plan ports forbids exactly that — any `readme.md`, case-insensitively, outside the project root.

**Why this made the task harder:** The pi guardrail folders need READMEs to match repository convention, which means writing files that the guardrail in the adjacent folder exists to prevent. Following either rule breaks the other.

**What was tried:** Followed the repository convention (`README.md` per guardrail folder), since consistency with 20 existing siblings beats consistency with one rule the repository has never applied to itself.

**What would improve this:** Either an `allowPaths` entry in this repository's own `harness/readme-name-guardrail/config.json` making the exemption explicit and visible, or a decision that plugin-folder READMEs are renamed on the `<name>-readme.md` pattern. Out of scope here, but it should be somebody's decision rather than a standing contradiction.

**What I think:** The guardrail's rule is the better one and the repository is the outlier — but changing 20 filenames is a separate story, not a side effect of adding pi support.
