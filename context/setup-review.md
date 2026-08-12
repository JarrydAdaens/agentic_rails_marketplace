---
name: marketplace-setup-review
description: Answers to the seven verification questions in the design doc (section 7), recorded during initial repository setup against current vendor documentation.
metadata:
  version: "1.1"
  date: "2026-07-10"
---

# Setup Review — Design §7 Verification Answers

> **2026-08-12 update:** Cursor is now the third supported marketplace host,
> using `.cursor-plugin/marketplace.json`, per-plugin Cursor manifests, native
> camel-case hook schemas, plugin-relative commands, and `mcp.json`. The
> installed Cursor CLI registers Git marketplaces with
> `agent plugin marketplace add <git-url>`. The advisor pair was consolidated
> into one portable `advisor-guardrail`; the WPF and game verifiers moved to
> `jarryds-agent-marketplace`. The original setup notes below remain useful as
> Claude/Codex history but no longer describe the complete repository.

Verified against the Claude Code docs (code.claude.com/docs, plugins reference
and plugin-marketplaces pages) and the Codex plugin docs
(developers.openai.com/codex/plugins/build) on 2026-07-10. Both plugin systems
move; re-verify paths and commands before structural changes.

## 1. Claude marketplace layout — confirmed, as proposed

`.claude-plugin/marketplace.json` at the repo root, with required `name`
(kebab-case; users type it in `/plugin install <plugin>@<marketplace>`),
`owner.name`, and `plugins[]` (each entry: required `name` + `source`; a
relative source must start with `./` and resolves against the marketplace
root). Per-plugin manifest is `.claude-plugin/plugin.json` inside the plugin
folder; `name` is its only required field. Validation: `claude plugin validate .`.

## 2. Codex marketplace layout — confirmed, one correction

Repo catalog at `.agents/plugins/marketplace.json` as proposed (personal
catalog would be `~/.agents/plugins/marketplace.json`). Codex also reads
`.claude-plugin/marketplace.json` as a legacy fallback, but we ship the native
file. Correction to the proposal: the per-plugin manifest is
`.codex-plugin/plugin.json` with **required `name`, `version`, and
`description`**. Local plugin sources use
`{"source": "local", "path": "./plugins/<name>"}`, resolved against the
marketplace root, not the `.agents/plugins/` folder.

## 3. Shared-payload pointer mechanism — adjusted: no `shared/` folder

Both tools natively discover the same default component directories at the
plugin root: `skills/<name>/SKILL.md` and `hooks/hooks.json` (Claude also
`agents/`, `commands/`, `.mcp.json`; Codex also `.mcp.json`, `.app.json`).
The default directories therefore *are* the shared payload — authored once,
zero pointer configuration. A `shared/` folder with per-tool path pointers
would add indirection without removing any duplication, so it was dropped.
Both manifests can point at custom paths if a future plugin ever needs it
(string/array fields `skills`, `hooks`, etc.).

Hard constraint discovered: installed plugins are **copied to a cache**
(`~/.claude/plugins/cache`) and cannot reference files outside their own
folder — no `../` paths, no cross-plugin sharing. Hook commands must use
`${CLAUDE_PLUGIN_ROOT}`.

## 4. Private-repo install — confirmed, local clone recommended for now

Claude Code uses existing git credential helpers for manual installs from
private repos; background auto-updates need `GITHUB_TOKEN`/`GH_TOKEN` (or the
GitLab/Bitbucket equivalents) in the environment because credential prompts
are suppressed at startup. The local-clone workaround is first-class, not a
hack: `/plugin marketplace add <local-path>` registers the clone directly,
and `/plugin marketplace update agentic-rails` refreshes after a `git pull`.
While this repo is private and single-user, the local clone is the
recommended registration form on every machine.

## 5. Hook trust behavior — confirmed

Both tools treat plugin hooks and MCP servers as high-trust and require the
user to review/approve them at install; they are not automatically trusted.
Users installing `advisor-guardrail` approve three Python hooks
(PreToolUse gate, PostToolUse marker, SessionStart cleanup/context). This
prompt is the deliberate trust gate — plugin READMEs say what will be asked.

## 6. Graceful degradation — confirmed with a caveat

A marketplace entry whose source fails to resolve breaks only that plugin's
install, not the marketplace. Within a plugin, malformed component files
degrade differently: a skill/agent file with bad YAML frontmatter loads
without metadata, but a **malformed `hooks/hooks.json` prevents the whole
plugin from loading**. `claude plugin validate .` catches both classes before
commit; running it is part of the publishing checklist.

## 7. Naming convention — decided

`<domain>-<subject>-<kind>`: domain = the surface the plugin applies to
(`game-`, `wpf-`), kind = `-verifier` (pass/fail acceptance check),
`-gate` (evaluator-run gate), or `-guardrail` (hook-enforced rail).
Domain-neutral plugins omit the domain prefix — the advisor guardrail applies
to every session, so it is `advisor-guardrail`, not `quota-advisor-guardrail`
(its origin name) or `rails-advisor-guardrail` (the marketplace already
namespaces installs as `<plugin>@agentic-rails`). Existing verifier names
already complied and were kept. Applied identically in both catalogs. Version fields: omitted in Claude manifests (commit-SHA versioning,
every push is an update); required and maintained in Codex manifests.

## Conversion notes (first three plugins)

- **`advisor-guardrail`** replaces the `rails-advisor-setup` installer
  skill from `agentic_rails_tooling`. The installer's copy/merge steps
  (settings.json merge, CLAUDE.md append, .gitignore merge) are all replaced
  by native mechanisms: hooks register via `hooks/hooks.json`, the agent ships
  in `agents/`, the protocol is injected by a SessionStart hook, and consult
  markers moved from the project's `.claude/` folder to the system temp
  directory so no .gitignore entry is needed. Claude-only.
- **`game-golden-screenshot-verifier`** runner paths changed: per-project
  files (config, driver, goldens, `last-run/`) now resolve relative to the
  config file rather than the runner, because the runner executes from the
  plugin cache instead of a copy inside the project.
- **`wpf-visual-quality-gate`** gate document now stays in the plugin; the
  per-project seam (the Project Defaults table) moved to a small defaults
  file the target project creates at adoption time.
