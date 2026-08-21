---
name: pi-agentic-ide
description: Durable reference for the Pi agentic IDE — what it is, how it is installed on this machine, its extension and package model, and the spike findings that establish how Agentic Rails guardrails can be ported to it.
metadata:
  version: "0.1"
  status: "Spike output — verified against pi 0.84.2"
  owner: "Jarryd Adaens"
  repo: "agentic_rails_marketplace"
  pi_version_verified: "0.84.2"
  verified_on: "16 August 2026"
---

# Pi — Agentic IDE Reference

Working knowledge of **Pi**, the fourth agentic host Agentic Rails targets. Everything
here was verified against **pi 0.84.2** on 16 August 2026, either from the copy of the
official documentation that ships inside the installed package or from a live spike on
this machine. Where a claim is documentation-only, it says so.

Pi moves fast. Re-verify against the shipped docs before trusting a version-sensitive
detail — the package carries its own `docs/` folder, which is the authoritative,
version-matched source and is always preferable to the website.

---

## 1. What Pi Is

Pi is a terminal coding agent from **Earendil Inc.**, distributed as the npm package
`@earendil-works/pi-coding-agent`. It reads files, writes code, edits files, and runs
shell commands inside a project directory. Its stated design philosophy:

> "Pi keeps the core small and pushes workflow-specific behavior into extensions,
> skills, prompt templates, and packages."

That sentence is the whole reason it fits Agentic Rails. Pi has no built-in guardrail
system; it has a small, sharp extension API that a guardrail can be written against.

### How it differs from the other three hosts

| | Claude Code / Codex / Cursor | Pi |
| --- | --- | --- |
| Guardrail unit | Plugin with a host manifest (`.claude-plugin/plugin.json` etc.) | **Extension** — a TypeScript module |
| Guardrail language | Shell / PowerShell / Python hook scripts | **TypeScript**, run in-process |
| Hook transport | Subprocess, JSON over stdin/stdout | **In-process function call** — no serialization, no stdin, no BOM |
| Distribution unit | Plugin listed in a `marketplace.json` catalog | **Package** — an npm-shaped folder |
| Catalog file | Yes, per host | **No such thing** |
| MCP | Supported | **Not present in this build** |

Two of those rows matter enormously in practice:

- **No hook subprocess.** The entire class of bugs Agentic Rails has fought on Windows —
  cp1252 mangling, the Cursor UTF-8 BOM on hook stdin, PATH resolution for `uv` and the
  vendor CLIs — simply does not exist for a pi guardrail's own plumbing. Handlers are
  TypeScript functions called in-process. (PATH resolution still matters when a guardrail
  *spawns* an external CLI, e.g. the advisors.)
- **No marketplace catalog.** Pi has no analog to `marketplace.json`. There is nothing to
  register and nothing to browse per-repository. Distribution is npm/git/local-path
  packages, and the public "gallery" at `pi.dev/packages` is just an npm keyword search
  for `pi-package`. **An "Agentic Rails marketplace for pi" is therefore a package, not a
  marketplace.**

---

## 2. Installation and Runtime on This Machine

Verified facts about the local install, useful because pi is deliberately self-contained.

| Fact | Value |
| --- | --- |
| Version | `0.84.2` |
| Package root | `C:\Users\Jarry\AppData\Local\pi-node\current\node_modules\@earendil-works\pi-coding-agent` |
| Launchers | `C:\Users\Jarry\AppData\Local\pi-node\current\pi.cmd` (also `pi`, `pi.ps1`) |
| Bundled runtime | Pi ships **its own Node** at `pi-node\current\node.exe` — it does not use the system Node, pnpm, or Volta |
| Not on PATH | `where.exe pi` finds nothing; the launcher directory must be added to PATH to invoke it from a script |
| Config directory | `~/.pi/agent/` |
| Settings | `~/.pi/agent/settings.json` |
| Model catalog | `~/.pi/agent/models.json` |
| Credentials | `~/.pi/agent/auth.json` |
| Sessions | `~/.pi/agent/sessions/<mangled-project-path>/` |

### Local model configuration

Pi here runs against a **local rig**, not a frontier API:

```json
{
  "defaultProvider": "ai-rig",
  "defaultModel": "qwen3.8-27b-q4km"
}
```

The `ai-rig` provider points at `http://192.168.2.175:1234/v1` (`openai-completions` API,
`supportsDeveloperRole: false`), serving `qwen3.8-27b-q4km` and `muse-glimmer-30b-q4km`,
both at **131,072 context / 32,768 max output**.

That 131k window is the single most important design constraint for anything written for
pi. A guardrail that injects a large payload — a full diff, a verbose review, a long
protocol document — spends the operator's context on plumbing. Every guardrail written
for pi must budget its output explicitly.

### Bundled documentation and examples

The installed package carries the authoritative version-matched docs and, more usefully,
a large set of working example extensions:

- `<package-root>/docs/` — 32 markdown files, including a 2,992-line `extensions.md`
- `<package-root>/examples/extensions/` — ~70 runnable examples

The examples that map directly onto Agentic Rails guardrail shapes:

| Example | Pattern it demonstrates |
| --- | --- |
| `permission-gate.ts` | Blocking a dangerous `bash` command, with a UI confirm and a non-interactive fallback |
| `protected-paths.ts` | Blocking `write`/`edit` by path |
| `confirm-destructive.ts` | Confirmation before a destructive action |
| `dirty-repo-guard.ts` | Refusing to proceed against a dirty working tree |
| `auto-commit-on-exit.ts` | Doing work on session teardown |
| `subagent/` | Running a nested agent |
| `handoff.ts` | Passing work to another session |
| `structured-output.ts` | Getting a machine-readable result back from a model |

Read these before writing a new guardrail. They are the shortest path to idiomatic pi.

---

## 3. The Extension Model

An extension is a TypeScript (or JavaScript) module with a default-exported factory that
receives an `ExtensionAPI`:

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("Extension loaded!", "info");
  });
}
```

### Where extensions are found

- `~/.pi/agent/extensions/*.ts` — global
- `.pi/extensions/*.ts` — project-local, **loaded only after the project is trusted**
- Anything listed in the `extensions` / `packages` arrays in `settings.json`
- `pi -e <path-or-source>` — load for one run without installing

Both a single file (`my-ext.ts`) and a directory (`my-ext/index.ts`) work. A directory
with its own `package.json` may carry dependencies.

### Security posture

The docs are blunt about this, and it should be quoted in any README that ships a pi
extension:

> "Extensions run with your full system permissions and can execute arbitrary code.
> Only install from sources you trust."

### Dependency rules for a shipped package

Pi bundles its own core packages. If an extension imports any of these, they go in
`peerDependencies` with a `"*"` range and must **not** be bundled:

`@earendil-works/pi-ai`, `@earendil-works/pi-agent-core`,
`@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `typebox`.

Real third-party runtime dependencies go in `dependencies`; pi runs `npm install` for
npm- and git-sourced packages. A guardrail that only shells out to a CLI and reads git
state needs **zero** dependencies.

---

## 4. Events

The lifecycle, reproduced from the shipped `docs/extensions.md`:

```
pi starts
  ├─► project_trust          (user/global and CLI extensions only)
  ├─► session_start
  └─► resources_discover

user sends prompt
  ├─► input                  (can intercept, transform, or handle)
  ├─► before_agent_start     (can inject a message, modify the system prompt)
  ├─► agent_start
  │   ┌─── turn (repeats while the LLM calls tools) ───┐
  │   ├─► turn_start
  │   ├─► context                        (can modify messages)
  │   ├─► before_provider_headers / before_provider_request / after_provider_response
  │   │     ├─► tool_execution_start
  │   │     ├─► tool_call                (CAN BLOCK)
  │   │     ├─► tool_execution_update
  │   │     ├─► tool_result              (CAN MODIFY)
  │   │     └─► tool_execution_end
  │   └─► turn_end
  ├─► agent_end              (pi may still retry, compact, or run queued follow-ups)
  └─► agent_settled          (pi will NOT continue automatically)

exit / /new / /resume / /fork
  └─► session_shutdown
```

### The four events that carry Agentic Rails guardrails

**`tool_call` — the deny hook.** Fires before a tool executes. Returns
`{ block: true, reason?: string, terminate?: boolean }`. `event.input` is **mutable**, so
a handler can patch arguments in place instead of blocking. Later handlers see earlier
mutations, and **no re-validation happens after a mutation**. `terminate` applies only to
a blocked call, and the agent stops early only when every finalized result in the batch
is terminating.

Use `isToolCallEventType("bash", event)` to narrow and get typed inputs.

**`agent_settled` — the wrap-up hook.** The correct hook for a completion gate or review
bot. `agent_end` is wrong for that purpose: pi may still auto-retry, auto-compact and
retry, or process queued follow-up messages after `agent_end`. `agent_settled` is the
event that means "pi will not continue on its own."

**It is also reentrant, and both intuitive loop guards are useless — see §9.6 and §9.7
before writing anything against it.** Injecting a message from this handler starts another
agent run, which settles again.

**`before_agent_start` — the context-injection hook.** Can inject a persistent message
into the session and rewrite the system prompt for the turn. `event.systemPromptOptions`
exposes the structured inputs pi used (custom prompt, selected tools, tool snippets,
guidelines, context files, skills), so an extension can make informed changes rather than
blind concatenation. System-prompt edits chain across handlers.

**`session_start` / `session_shutdown` — the session boundary.** Session-scoped state is
set up in one and cleaned up in the other. `session_shutdown` carries a `reason` of
`"quit" | "reload" | "new" | "resume" | "fork"`.

### Other events worth knowing

- `tool_result` — chains like middleware; handlers return partial patches (`content`,
  `details`, `isError`, `usage`), and omitted fields keep their current values.
- `user_bash` — fires for operator-typed `!command` / `!!command`. **Distinct from the
  agent's `bash` tool.** A guardrail that means to restrain the *agent* must not hook
  this, or it restrains the human.
- `input` — sees raw text before `/skill:` and `/template` expansion; returns
  `continue` | `transform` | `handled`.
- `project_trust` — returns `{ trusted: "yes" | "no" | "undecided", remember?: boolean }`.
  The first yes/no wins and suppresses pi's built-in prompt.

### Parallel-tool caveat

In the default parallel execution mode, sibling tool calls from one assistant message are
preflighted sequentially and then executed concurrently. A `tool_call` handler is **not**
guaranteed to see sibling results from that same message in `ctx.sessionManager`. Any
guardrail whose decision depends on "has X already happened this turn" must hold its own
state, not read it back out of the session.

---

## 5. Custom Tools — the MCP Replacement

This build of pi has no MCP. It does not need one for the Agentic Rails advisor pattern,
because `pi.registerTool()` registers a first-class tool that the model can call directly:

```typescript
pi.registerTool({
  name: "my_tool",
  label: "My Tool",
  description: "What it does (shown to the LLM)",
  promptSnippet: "Brief one-liner for the Available tools section",
  promptGuidelines: ["Use my_tool when the user asks for X"],
  parameters: Type.Object({ /* typebox schema */ }),
  async execute(toolCallId, params, signal, onUpdate, ctx) {
    onUpdate?.({ content: [{ type: "text", text: "Progress..." }] });
    return {
      content: [{ type: "text", text: "Result for the LLM" }],
      details: { data: "for rendering" },
    };
  },
});
```

This is strictly better than the shell-CLI-over-stdin protocol the Cursor and Codex
advisor guardrails were forced into: no protocol document to teach the model, no stdin
JSON contract, no marker files, and the tool shows up in the tool list natively. The
`promptSnippet` and `promptGuidelines` fields let a guardrail control its own footprint
in the system prompt — which is exactly the lever needed on a 131k local model.

Built-in tools can be overridden by registering a tool of the same name. Built-in tool
names are: `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls`.

### Built-in tool input fields

A write gate reads these off `event.input`, so the exact field names matter. Verified
against `dist/core/tools/*.d.ts` in the installed package:

| Tool | Input |
| --- | --- |
| `write` | `{ path, content }` |
| `edit` | `{ path, edits: [{ oldText, newText }] }` |
| `bash` | `{ command, timeout? }` |
| `read` | `{ path, offset?, limit? }` |

Note **`path`, not `file_path`.** Claude Code and Cursor hook payloads use `file_path`,
and a guardrail ported by eye from those hosts will read `undefined` and silently pass
everything. That failure is invisible — the gate looks installed and does nothing.

### Useful `ExtensionAPI` and context members

| Member | Purpose |
| --- | --- |
| `pi.on(event, handler)` | Subscribe to an event |
| `pi.registerTool(def)` | Register an LLM-callable tool |
| `pi.registerCommand(name, opts)` | Register a `/command` |
| `pi.sendUserMessage(content, opts)` | Queue a user message (drives the agent) |
| `pi.sendMessage(msg, opts)` | Inject a custom message |
| `pi.appendEntry(customType, data)` | Persist data into the session |
| `pi.exec(command, args, opts)` | Run a subprocess |
| `pi.registerFlag(name, opts)` | Add a CLI flag |
| `ctx.ui` | `select()`, `confirm()`, `input()`, `notify()`, `setStatus()`, `setWidget()` |
| `ctx.hasUI` | **False in print/RPC mode** — always check before prompting |
| `ctx.mode` | `"tui" \| "rpc" \| "json" \| "print"` |
| `ctx.cwd` | Working directory |
| `ctx.signal` | Abort signal — pass to `fetch`/subprocess so Esc cancels nested work |
| `ctx.isIdle()` / `ctx.abort()` | Agent run state |
| `ctx.getContextUsage()` | Current context consumption |
| `ctx.sessionManager` | Read-only session access |

---

## 6. Packages — the Distribution Model

A pi package is an npm-shaped folder that declares its resources in `package.json` under
a `pi` key:

```json
{
  "name": "my-package",
  "keywords": ["pi-package"],
  "pi": {
    "extensions": ["./extensions"],
    "skills": ["./skills"],
    "prompts": ["./prompts"],
    "themes": ["./themes"]
  }
}
```

Paths are relative to the package root and support globs and `!exclusions`. With no `pi`
manifest, pi auto-discovers from convention directories: `extensions/` (`.ts`, `.js`),
`skills/` (`SKILL.md` folders and top-level `.md`), `prompts/` (`.md`), `themes/`
(`.json`).

### Sources and commands

```bash
pi install npm:@foo/bar@1.0.0
pi install git:github.com/user/repo@v1
pi install /absolute/path/to/package
pi install ./relative/path/to/package

pi remove npm:@foo/bar
pi list                     # installed packages
pi update --extensions      # update packages, reconcile pinned git refs
pi config                   # TUI to enable/disable individual resources
pi -e <source>              # try without installing (temp dir, one run)
```

`install`/`remove` write to `~/.pi/agent/settings.json` by default; `-l` targets
`.pi/settings.json` instead. Project settings can be committed, and pi installs missing
packages automatically on startup **once the project is trusted**.

### The constraint that shapes everything

**A git source clones the whole repository and loads from its root. There is no
subdirectory selector.** `git:github.com/user/repo@ref` is the entire addressing scheme;
there is no `#path/to/subdir` syntax. Consequences:

- A multi-guardrail monorepo cannot expose per-guardrail git installs. Per-guardrail
  install-and-remove is only reachable via **local paths** (one `pi install` per folder,
  from a clone) or by **one repository per guardrail**.
- A single repo-root `package.json` whose globs reach into subfolders makes the whole
  repository installable in one command — and per-resource granularity then comes from
  **filtering**, not from install/remove.

Git refs are **pinned** to tags or commits. `pi update --extensions` reconciles an
existing clone to the configured ref but does not move it to a newer one; moving requires
`pi install git:host/user/repo@new-ref`. When reconciliation changes the checkout, pi
resets and cleans the clone and re-runs `npm install` if a `package.json` exists.

Clones land in `~/.pi/agent/git/<host>/<path>` (global) or `.pi/git/<host>/<path>`
(project); npm installs in `~/.pi/agent/npm/` or `.pi/npm/`.

### Filtering — the granularity lever

```json
{
  "packages": [
    "npm:simple-pkg",
    {
      "source": "npm:my-package",
      "extensions": ["extensions/*.ts", "!extensions/legacy.ts"],
      "skills": [],
      "prompts": ["prompts/review.md"],
      "themes": ["+themes/legacy.json"]
    }
  ]
}
```

Omit a key to load all of that type; `[]` loads none; `!pattern` excludes; `+path` and
`-path` force-include and force-exclude exact paths. **Filters only narrow what the
manifest already allows.** `pi config` is the interactive front end for this and is how
an operator turns one guardrail off without uninstalling the package.

### Scope and identity

A package may appear in both global and project settings. The project entry wins unless
it sets `autoload: false`, in which case it is applied as a delta over the global entry.
Identity is the npm package name, the git repository URL without its ref, or the resolved
absolute path.

---

## 7. Skills, Prompts, Context Files

**Skills** are discovered from `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`,
`.agents/skills/`, package `skills/` directories, settings, and `--skill`. A skill is a
`SKILL.md` with YAML frontmatter carrying `name` and `description`; names are 1–64 chars,
lowercase `a-z0-9-`, no leading/trailing or consecutive hyphens. At startup pi puts every
skill's name and description in the system prompt and reads the full file on demand.
Invoked as `/skill:name [args]`.

Notably, **pi allows a skill's `name` to differ from its directory name**, which Claude
Code does not. `~/.agents/skills/` is a shared, harness-neutral location.

**Context files** load from `~/.pi/agent/AGENTS.md` (global) and `AGENTS.md` or
`CLAUDE.md` in the project or any parent directory. `AGENTS.override.md` takes precedence
when present. `-nc` / `--no-context-files` disables discovery.

That last point matters for Agentic Rails: **pi reads the existing `AGENTS.md` files
verbatim.** The left rail already works on pi with no porting at all.

---

## 8. CLI Surface

```
pi                            # interactive
pi -c                         # continue most recent session
pi -r                         # browse sessions
pi -p "prompt"                # one-shot, non-interactive
pi @file.md "request"         # reference files
!command                      # run a shell command inside the chat
```

Selected flags (full list from `pi --help` on 0.84.2):

| Flag | Meaning |
| --- | --- |
| `--provider` / `--model` / `--thinking` | Model selection; thinking is `off`…`max` |
| `-p`, `--print` | Non-interactive; `ctx.hasUI` is false |
| `--mode <text\|json\|rpc>` | Output mode |
| `-e`, `--extension <path>` | Load an extension (repeatable) |
| `-ne`, `--no-extensions` | Disable discovery; explicit `-e` still works |
| `--skill`, `--prompt-template`, `--theme` | Load resources directly |
| `-t`/`-xt`/`-nt`/`-nbt` | Tool allowlist / denylist / none / no built-ins |
| `--no-session` | Ephemeral run |
| `-a` / `-na` | Trust / ignore project-local files for this run |
| `--append-system-prompt` | Append text or file contents (repeatable) |
| `--offline` | Disable startup network operations |

Programmatic surfaces exist and are documented but were not exercised in this spike:
an SDK, RPC mode, a JSON event-stream mode, and TUI components.

---

## 9. Spike Findings (live, on this machine)

Five things were proven by running pi rather than by reading about it.

### 9.1 `tool_call` blocking works end to end

A throwaway extension that returns `{ block: true, reason }` for `bash` commands matching
a python pattern was loaded with `pi -e ./block-python.ts` and driven with `-p`. The block
fired, the model saw the reason, and it reported the interception accurately in its final
answer. **The core deny mechanism a guardrail needs is real and reliable.**

### 9.2 A bad pattern makes a local model thrash — six times

The spike regex was deliberately naive (any occurrence of `python`), so it also blocked
`uv run python --version` — the very remedy the deny message recommended. The local model
did not give up. It burned **six** tool calls trying variations before concluding, in its
own words, that "any command containing the string `python` gets intercepted."

Two lessons, and they are the most valuable output of this spike:

1. **A false positive on a local model is not a minor annoyance; it is a loop.** The
   existing PowerShell `python-uv-guardrail` avoids this properly — it splits the command
   on shell control operators, skips wrappers (`sudo`, `env`, `time`, `nice`) and inline
   `VAR=value` assignments, resolves the *leading executable* of each segment, strips path
   and `.exe`, and exempts segments already led by `uv`/`uvx`. **Port that logic, not a
   regex.**
2. **A deny message that recommends a remedy must be verified not to block that remedy.**
   That belongs in the test suite as an explicit case, not as a comment.

### 9.3 `terminate: true` stops the thrash

The second spike extension blocked `git push` with `terminate: true`. The agent stopped
immediately — one block, no retry loop, in direct contrast to 9.2. For a prohibition that
has **no** legitimate remedy the agent can reach (git push, which no agent should ever
perform), `terminate: true` is the correct setting. For a prohibition with a remedy (use
`uv`), it is wrong — the agent should retry, correctly.

### 9.4 Local-path package install/remove works, and stores a relative path

A two-extension package folder was installed with `pi install <abs path>`, both extensions
loaded and fired, and `pi remove` cleanly reverted the settings file.

One wrinkle worth recording: pi **normalizes** the stored path rather than keeping what
you typed. It writes a path relative to the settings file when one is expressible, and an
absolute path when it is not. Both were observed:

```json
{ "packages": ["..\\..\\AppData\\Local\\Temp\\pi-spike\\pkg"] }        // C: package, C: settings
{ "packages": ["D:\\Code Projects\\agentic_rails\\agentic_rails_marketplace"] }  // D: package
```

The second was measured on 17 August 2026 during the Phase 5 install round trip and
corrects the original "always relative" reading of this finding.

Either form is a portability footgun, for different reasons: the relative form binds the
install to the settings file's own location, so a settings file copied to another machine
resolves it somewhere unintended; the absolute form is machine-bound outright. **Document
the git source as the portable install and a local path as a development convenience
only.**

### 9.5 Pi's `tool_call` fails **closed**, not open

From the shipped `docs/extensions.md` §Error Handling, quoted in full because it is three
lines and every one of them matters:

- "Extension errors are logged, agent continues"
- **"`tool_call` errors block the tool (fail-safe)"**
- "Tool `execute` errors must be signaled by throwing; the thrown error is caught,
  reported to the LLM with `isError: true`, and execution continues"

The middle line **inverts the Agentic Rails discipline**. Every PowerShell and Python
guardrail in this repository exits 0 on an internal error so that a hook bug can never
block the tool it guards. Pi does the opposite: an unhandled throw inside a `tool_call`
handler blocks the call. Pi calls that fail-safe, and for a permission gate it is the
defensible default — but it means a bug in a pi guardrail wedges `bash` for the whole
session rather than quietly disarming.

Consequence: wrapping every `tool_call` handler body in `try/catch` and returning
`undefined` is **mandatory**, not defensive style. It is the only thing standing between a
typo and an unusable session.

### 9.6 `agent_settled` is reentrant, and the obvious guard does not work

Measured, not assumed. A probe extension hooked `agent_settled` and called
`pi.sendUserMessage()` from the handler, capped at three injections. Driven through **RPC
mode** (a persistent session, unlike `-p`), the result was unambiguous:

```
[PROBE] agent_settled #1 inFlight=false isIdle=true mode=rpc
[PROBE] injecting user message #1
[PROBE] agent_settled #2 inFlight=false isIdle=true mode=rpc
[PROBE] injecting user message #2
[PROBE] agent_settled #3 inFlight=false isIdle=true mode=rpc
[PROBE] injecting user message #3
```

Three full agent runs. The cycle stopped only because the hard counter stopped it.

Two guards that look sensible and **are not**:

- **An in-flight boolean is useless.** `inFlight` read `false` on every reentrant fire.
  `sendUserMessage` resolves as soon as the message is queued, long before the agent run
  it triggers completes, so the `finally` block clears the flag before the next
  `agent_settled` arrives.
- **`ctx.isIdle()` does not discriminate.** It read `true` on every fire, including the
  reentrant ones.

What actually works is a **hard cycle counter**, and it works reliably. A content
fingerprint helps only when the tree is unchanged; if the agent edits files each cycle the
fingerprint differs every time and stops nothing. Any wrap-up guardrail that injects
context must treat the counter as its primary guard, not its backstop.

### 9.7 Print mode cannot host an *injecting* wrap-up guardrail — but it can host an awaited one

The original probe under `pi -p` produced exactly one `agent_settled`, and the injected
message never ran — the session shut down first, and the deferred `sendUserMessage` threw:

> "This extension ctx is stale after session replacement or reload."

**That result was correct but the conclusion drawn from it was too broad.** It shows that
*injection* cannot work in print mode: `-p` is documented as "process prompt and exit", so
there is no further agent run for an injected message to drive.

It does **not** show that the handler is skipped. Measured 17 August 2026, a second probe
whose `agent_settled` handler awaited an 8-second sleep and then wrote a file:

```
[PROBE] agent_settled entered; sleeping 8s
[PROBE] agent_settled completed after sleep
```

Both markers were written, and the prompt's own output appeared after them. **Pi awaits an
async `agent_settled` handler before exiting in print mode.**

The practical consequence is significant for orchestration: a wrap-up guardrail can run a
full external review in `pi -p` and persist its verdict to disk, provided it **returns its
promise so pi awaits it** and **reports rather than injects**. Reject becomes a written
verdict for the caller instead of a bounced-back message.

A guardrail that stands down on `ctx.mode === "print"` is therefore being more
conservative than necessary — and note that such a check is also the wrong shape, since
`--mode json` is equally non-interactive and would take the injecting path. The correct
condition is "do not inject in any non-interactive mode", not "do nothing in print mode".

### 9.8 Pi's bundled Node runs TypeScript directly — no build step, no dev dependency

`pi-node\current\node.exe` is **Node v22.23.2**, new enough that type stripping is on by
default. Verified working:

```bash
node.exe some-extension.ts             # runs
node.exe --test "**/*.test.ts"         # runs node:test suites, quote the glob
```

Verified **not** working, with the exact failure:

| Attempt | Result |
| --- | --- |
| `node --test <directory>` | Fails — the default test-file glob does not match `.ts` |
| `enum Color { Red }` | `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` — enums need transformation, not erasure |
| `import { seg } from "./t"` | `ERR_MODULE_NOT_FOUND` — relative imports need an explicit `.ts` extension |

Namespaces fail for the same reason as enums, and type-only imports must use
`import type` so they erase cleanly.

None of that is a real constraint here, because **pi's own bundled examples already write
in exactly that style** — `examples/extensions/plan-mode/index.ts`,
`subagent/index.ts`, and `doom-overlay/index.ts` all import relative modules with explicit
`.ts` extensions and use `import type`. One source style satisfies both pi's loader
(jiti) and Node's stripper, and a repository can test TypeScript guardrails with zero dev
dependencies.

### 9.9 A git install of this repository is cheap

6.0 MB working tree, 2.1 MB of git objects, 376 tracked files, no cache directories
tracked. Pi cloning the whole repository — including the three host trees it has no use
for — costs roughly 8 MB. Not worth optimizing.

### 9.10 There is no marketplace to register

`pi list` on a fresh install reports "No packages installed." There is no
`marketplace add` command, no catalog file, and no per-repository registry. The
`agentic_rails_marketplace` repository cannot be "registered" with pi the way it is with
Claude Code, Codex, and Cursor. It can only be **installed as a package**.

---

## 10. Implications for Agentic Rails

Recorded here so the next agent does not have to re-derive them.

1. **`plugins/pi/` is not a fourth peer of the other three roots.** The others contain
   plugin folders with host manifests, listed in a catalog. Pi has neither manifests nor a
   catalog. The pi root is a set of extension source folders reached by globs from a
   single package manifest.
2. **The root package.json is a repository-level change.** Whatever shape is chosen, pi
   support touches the repository root, not just a subtree — unlike adding a plugin to an
   existing host root. It also means pi runs `npm install` at the repository root when
   reconciling a git clone.
3. **The existing cross-host test suite hard-codes `HOSTS = ("claude", "codex", "cursor")`**
   and asserts that every plugin folder carries exactly one host manifest. `plugins/pi/`
   violates that by construction and must be excluded from the host-matrix tests and given
   its own structural test.
4. **Guardrail logic ports; guardrail plumbing does not.** The decision logic in the
   PowerShell and Python hooks (what counts as a bare interpreter, what counts as a
   forbidden readme path, what the deny message says) is the valuable part and should be
   reproduced faithfully. The plumbing around it — stdin decoding, BOM stripping, JSON
   response envelopes, `uv` and CLI path resolution, marker files — is dead weight on pi.
5. **The advisor guardrails get simpler and better.** `pi.registerTool()` replaces the
   entire MCP-or-stdin-protocol problem. There is no protocol document to inject and no
   marker-file dance; the write gate just watches for its own tool having been called.
6. **The 131k budget is a hard design input.** Injected context, advisor replies, and
   review output all have to be capped deliberately. A guardrail that returns an
   unbounded external-model response is a bug on this host even though it is merely
   untidy on the others.
7. **The harness seam convention still applies.** A pi guardrail should read its optional
   per-project config from the same `harness/<guardrail-name>/config.json` the other hosts
   use, so a project never grows a second config location for the same guardrail.
8. **Fail-open is not free on pi — it is hand-written.** The other hosts get it from
   `exit 0`. On pi, an unhandled throw in a `tool_call` handler *blocks* (§9.5), so every
   handler body must be wrapped and return `undefined` on an unexpected error. Treat a
   missing `try/catch` in a pi guardrail as a defect, not a style nit.
9. **A wrap-up guardrail needs a hard cycle counter and a print-mode stand-down.**
   `agent_settled` is reentrant, and both intuitive guards — an in-flight flag and
   `ctx.isIdle()` — are provably useless (§9.6). In `-p` the mechanism does not work at
   all (§9.7).
10. **TypeScript guardrails need no build step and no dev dependency.** Pi's bundled
    Node 22.23.2 runs and tests `.ts` directly, provided the source stays within erasable
    syntax and uses explicit `.ts` extensions on relative imports (§9.8) — which is the
    style pi's own examples already use.

---

## 11. Open Questions

Resolved on 16 August 2026 and moved into §9: extension error isolation (9.5),
`agent_settled` reentrancy (9.6), print-mode behavior (9.7), the TypeScript test story
(9.8), and clone size (9.9). What remains:

- **How does `pi config` present resources from a package whose extensions live several
  directories deep?** Filter paths are relative to the package root, so deep paths are
  presumably shown verbatim — legible, but unverified.
- **Is `AgentSession` (used directly from `@earendil-works/pi-coding-agent`) a better way
  to run a nested review model than spawning an external CLI?** `docs/rpc.md` explicitly
  recommends it over subprocess spawning for Node clients. It would keep a review inside
  pi's own runtime rather than shelling out to Claude — a different architecture worth
  evaluating before committing to the subprocess design.
- **Does `pi update --extensions` reconcile a local-path package at all?** Refs and
  reconciliation are documented for git and npm sources; a local path "points to disk
  without copying", so it presumably needs no update step. Unverified.
- **What is the token cost of a registered tool in the system prompt?** `promptSnippet`
  and `promptGuidelines` control it, but the actual per-tool overhead against a 131k
  window has not been measured — and it decides how many advisor guardrails can sensibly
  be installed at once.
