# agentic_rails_marketplace

The native plugin marketplace of the Agentic Rails framework. This repository
holds the agentic artifacts that have a **lifecycle** — verifiers and
guardrails, with the hooks that wire them into a tool — and distributes them
through each tool's own marketplace mechanism rather than by file copy. The
full rationale, boundaries, and vocabulary live in
[`context/design.md`](context/design.md); this file covers day-to-day use.

> **Boundary rule:** Kung Fu never deploys, copies, or otherwise manages this
> repository. Everything here is installed and removed through the native
> marketplaces of Claude Code and Codex, full stop.

## Registering the marketplace

Once per machine, per tool:

```shell
# Claude Code (interactive session or CLI)
/plugin marketplace add <git-url-or-local-path-to-this-repo>

# Codex
/plugin marketplace add <git-url-or-local-path-to-this-repo>
```

Both tools accept a local clone path (e.g. `D:\Code Projects\agentic_rails\agentic_rails_marketplace`),
which is the recommended form while the repo is private — it sidesteps
credential handling entirely, is instant to update (`/plugin marketplace update agentic-rails`
after a pull), and stays diffable. Git URLs also work; Claude Code uses your
existing git credential helpers for manual installs and needs a `GITHUB_TOKEN`
in the environment only for background auto-updates of private marketplaces.

Then install per plugin, per machine, as the work requires:

```shell
/plugin install game-golden-screenshot-verifier@agentic-rails
/plugin install wpf-visual-quality-gate@agentic-rails
/plugin install advisor-guardrail@agentic-rails
```

Update, enable, disable, and remove through the same `/plugin` surface. On
install, each tool asks you to review and trust any hooks a plugin registers —
that prompt is the expected, deliberate trust gate for guardrail plugins.

## Plugins

| Plugin | Kind | Tools | What it does |
| --- | --- | --- | --- |
| `game-golden-screenshot-verifier` | verifier | Claude Code, Codex | Launches a game, drives a deterministic scene, compares an OS-level screenshot against a versioned golden. Exit 0/1. |
| `wpf-visual-quality-gate` | verifier | Claude Code, Codex | Independent evaluator launches a WPF app, performs the changed interaction with real input, screenshot-verifies against packet criteria. |
| `advisor-guardrail` | guardrail | Claude Code only | Ships an `advisor` subagent plus hooks that deny the session's first write until the advisor has been consulted. |

`advisor-guardrail` is Claude-only because its payload is built on Claude
Code subagents and PreToolUse permission decisions; it is therefore absent from
the Codex catalog.

## Repository layout

```text
.claude-plugin/marketplace.json    # Claude Code catalog
.agents/plugins/marketplace.json   # Codex catalog
plugins/<plugin-name>/             # one folder per independently installable plugin
├── .claude-plugin/plugin.json     # Claude registration
├── .codex-plugin/plugin.json      # Codex registration (omitted for Claude-only plugins)
├── skills/ · agents/ · hooks/     # the payload, authored once
└── README.md
context/                           # design doc and setup review for this repo
```

**Project seams live in `harness/`.** A plugin ships the stable engine; the
consuming project owns one folder per adopted plugin —
`harness/<plugin-name>/` — holding everything project-specific (config,
goldens, drivers, defaults) plus git-ignored runtime output (`runs/`,
`last-run/`, `state/`). The same folder convention holds a project's local,
not-yet-promoted checks, so a check keeps its home as it graduates from
project experiment to installed plugin. The layer is defined in the
`agentic_rails_context_starter` repo's `harness/` template; each plugin's
README states exactly what its seam folder must contain.

One deliberate adjustment from the design doc's proposed shape (validated
against both vendors' docs, July 2026): there is no `shared/` payload folder.
Both tools natively discover `skills/` and `hooks/hooks.json` at the plugin
root, so those default component directories **are** the shared payload — a
`shared/` indirection would add pointer manifests without removing any
duplication. Details in [`context/setup-review.md`](context/setup-review.md).

## Naming convention

`<domain>-<subject>-<kind>`, all kebab-case, where **domain** is the surface
the plugin applies to (`game-`, `wpf-`…) so related plugins cluster in the
plugin browsers, and **kind** is the artifact type: `-verifier` for pass/fail
acceptance checks, `-gate` for evaluator-run gates, `-guardrail` for
hook-enforced behavioral rails. Domain-neutral plugins that apply to every
session omit the domain prefix (`advisor-guardrail`) — never invent one, and
never prefix with `rails-`: the marketplace already namespaces every install
(`<plugin>@agentic-rails`). A plugin's `name` is its stable identifier —
renaming later requires a `renames` migration entry in the Claude catalog, so
choose carefully.

## Publishing a new plugin

1. Author the payload under `plugins/<name>/` using the default component
   directories (`skills/`, `agents/`, `hooks/hooks.json`). Hook commands must
   reference their scripts via `${CLAUDE_PLUGIN_ROOT}` — installed plugins run
   from a cache, never from this repo, and cannot reference files outside
   their own plugin folder.
2. Add `.claude-plugin/plugin.json` (name only; **omit `version`** — plugins
   here are versioned by commit SHA, so every push is an update) and, for
   Codex-compatible plugins, `.codex-plugin/plugin.json` (name, version, and
   description are required there).
3. Register the plugin in `.claude-plugin/marketplace.json` and, if
   Codex-compatible, `.agents/plugins/marketplace.json`.
4. Validate with `claude plugin validate .`, then commit and push. The commit
   history is the version record.
