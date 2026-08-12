# AGENTS.md

This file provides repository guidance for agentic IDEs and coding agents working in this repository. It is vendor-neutral: Cursor, Claude Code, Codex, Windsurf, and other agents should treat it as the project-level instruction entry point. `CLAUDE.md` here simply imports this file.

## What this repository is

`agentic_rails_marketplace` is the fourth repository of the Agentic Rails framework: a **native plugin marketplace** that Claude Code, Codex, and Cursor register directly and install individual plugins from. It holds framework-neutral lifecycle guardrails rather than technology-stack-specific checks. Read `context/design.md` before reshaping anything — the boundaries are the point.

## Hard rules

- **Kung Fu never touches this repo.** No artifact here is deployed by file copy. Everything installs and uninstalls through each tool's native plugin marketplace mechanism.
- **Never edit installed copies.** Installed plugins live in a per-tool cache (e.g. `~/.claude/plugins/cache`). Edit here, commit, and let the marketplace update mechanism deliver the change.
- **A plugin cannot reference files outside its own folder.** Installs copy the plugin directory into a cache, so `../` paths break. Hook commands use `${CLAUDE_PLUGIN_ROOT}`; per-project state belongs in the target project or the system temp directory.
- **Project seams follow the harness convention.** Anything a consuming project must provide or that a plugin writes per project lives in that project's `harness/<plugin-name>/` folder (config, goldens, drivers, defaults; git-ignored `runs/`/`state/`/`last-run/` for runtime output). Plugins must not prescribe any other project-side location, and a missing seam must degrade to a silent skip, never an error — plugins are installed system-wide but adopted per project.
- **Do not set `version` in `.claude-plugin/plugin.json`.** Plugins are versioned by commit SHA so every push is an update. `.codex-plugin/plugin.json` requires a version field; bump it there when the payload changes meaningfully.
- **Plugin `name` is a stable identifier.** Renames require a `renames` migration map in `.claude-plugin/marketplace.json`; treat that map as append-only history.

## Layout and conventions

- One folder per plugin under `plugins/`, named `<domain>-<subject>-<kind>` (kinds: `-verifier`, `-gate`, `-guardrail`). Shared payload is authored once; thin `.claude-plugin/`, `.codex-plugin/`, and `.cursor-plugin/` manifests select host-specific hooks or MCP launchers.
- Host-specific adapters belong inside one stable plugin when they implement one capability. Manifests must prevent a host from loading another host's payload.
- Every plugin folder has a `README.md` stating what it does, what the consuming project must provide, and any known limitations.
- All three catalogs (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, `.cursor-plugin/marketplace.json`) must list every compatible plugin; keep them in sync when adding or removing plugins.
- File and folder names are kebab-case except tool-mandated names and language-idiomatic code files. American English throughout.
- Validate before committing: `claude plugin validate .` from the repo root.

## What does not belong here

Inert, copy-deployed artifacts — rules, skills without lifecycle, agents, memories, context templates — belong in the other three repositories (`agentic_rails_tooling`, `agentic_rails_context_starter`, `agentic_rails_memory`). If an artifact needs no install/uninstall behavior, it is not a plugin.
