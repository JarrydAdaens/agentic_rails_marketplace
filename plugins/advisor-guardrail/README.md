# advisor-guardrail

Actor–critic guardrail for Claude Code, delivered as a marketplace plugin: an
executor session (Opus/Sonnet) must consult a stronger, read-only `advisor`
subagent at decision points, with "consult before your first write" enforced
by a deterministic PreToolUse hook rather than left as advisory prose. This
replicates Anthropic's API-only advisor tool inside Claude Code on a Max
subscription. Full design rationale, native tool comparison, and accepted
trade-offs live in `references/advisor-design.md`.

**Claude Code only.** The payload is built on Claude Code subagents and
PreToolUse permission decisions, so this plugin has no Codex manifest and is
absent from the Codex catalog.

## What the plugin registers

| Component | Role |
| --- | --- |
| `agents/advisor.md` | The advisor subagent: read-only tools (Read/Grep/Glob), 120-word brevity contract, checkpoint-not-explorer role. Runs on Fable. |
| `hooks/advisor_gate.py` (PreToolUse) | Denies the session's first Write/Edit/MultiEdit/NotebookEdit until a consult marker exists. |
| `hooks/advisor_marker.py` (PostToolUse on Task/Agent) | Touches the per-session marker when the invoked subagent is the advisor (plain or plugin-namespaced). |
| `hooks/advisor_cleanup.py` (SessionStart) | Removes consult markers older than 24 hours. |
| `hooks/advisor_context.py` (SessionStart) | Prints `advisor-protocol.md` so the consult protocol enters the session's context. |

On install, Claude Code asks you to review and trust these hooks — that
prompt is the point of the guardrail being a plugin.

Everything the old installer skill copied or merged is now native: hook
registration replaces the `settings.json` merge, the SessionStart context
injection replaces the `CLAUDE.md` append, and consult markers moved from the
project's `.claude/` folder to the system temp directory
(`<temp>/claude-advisor-markers/`), so no `.gitignore` entry is needed.
Enable the plugin per project or globally through the standard `/plugin`
enablement scopes.

## What to expect after install

In each fresh session, the first file write is denied with an instructive
reason; it succeeds after one advisor consult. The deny is the feature
working, not an error.

## Model note

The advisor is pinned to `model: fable` in `agents/advisor.md`. If a machine's
plan or Claude Code version does not resolve the `fable` alias, change the
line to `opus` here in the marketplace copy (never in the installed cache) —
a Sonnet-executor/Opus-advisor pairing is still a genuine capability lift.

## Known limitations (accepted v1 trade-offs)

- **Bash is deliberately ungated** — reliably classifying read-only vs.
  state-changing shell commands in a hook is fragile; the protocol text
  covers Bash advisorily.
- **Per-session, not per-task**: a long multi-task session only forces one
  consult.
- The advisor sees only the structured consult payload, not the transcript;
  thin payloads produce poor advice. The payload contract in the protocol is
  the mitigation.
