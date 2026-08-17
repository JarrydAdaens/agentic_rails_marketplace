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

- Three manifest host roots — `plugins/claude/`, `plugins/codex/`, and `plugins/cursor/` — each holding only the plugins that host supports. A plugin available on more than one host is a separate copy under each host's root, not a shared payload — there is no cross-host branching in a plugin's own code, and no folder outside its host root is ever referenced.
- A fourth source root, `plugins/pi/`, is **not a peer** of the three. Pi has no per-plugin manifest and no catalog: the whole repository is **one pi package** declared by the root `package.json`, whose `pi.extensions` glob (`plugins/pi/*/extensions/*.ts`) reaches into each guardrail folder. Per-guardrail granularity on Pi comes from `pi config` filtering, not install-and-remove, because a pi git source clones the repository root with no subdirectory selector. `plugins/pi/shared/` is a library imported by the extensions and is deliberately not matched by the extension glob. Pi's install points at the checkout rather than copying a plugin folder, so the "no folder outside its host root" rule above applies to the three manifest hosts, not to `plugins/pi/`.
- `tests/test_cross_ide_guardrails.py` covers the three manifest hosts only; the `plugins/pi/` exclusion there is deliberate, not an oversight — do not add `pi` to its `HOSTS`. Pi's structure is covered by `tests/test_pi_package.py` and its behavior by the per-module `.test.ts` files run under Pi's bundled Node.
- Each plugin folder is named `<domain>-<subject>-<kind>` (kinds: `-verifier`, `-gate`, `-guardrail`) and carries exactly one host manifest: `.claude-plugin/` under `plugins/claude/`, `.codex-plugin/` under `plugins/codex/`, `.cursor-plugin/` under `plugins/cursor/`. A plugin folder with more than one `.*-plugin/` directory is a bug.
- Every plugin folder has a `README.md` stating what it does, what the consuming project must provide, and any known limitations.
- Each catalog (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, `.cursor-plugin/marketplace.json`) lists only the plugins in its own host root — `./plugins/<host>/<name>` — and nothing outside it.
- Pi extension sources stay within erasable TypeScript (no enums or namespaces), use explicit `.ts` extensions on relative imports, and use `import type` for type-only imports — the style Pi's own examples use, which is also what Pi's bundled Node can run and test directly.
- File and folder names are kebab-case except tool-mandated names and language-idiomatic code files. American English throughout.
- Validate before committing: `claude plugin validate .`, `uvx --with pytest pytest tests/ -q`, and `"C:\Users\Jarry\AppData\Local\pi-node\current\node.exe" --test "plugins/pi/**/*.test.ts"` from the repo root.

## What does not belong here

Inert, copy-deployed artifacts — rules, skills without lifecycle, agents, memories, context templates — belong in the other three repositories (`agentic_rails_tooling`, `agentic_rails_context_starter`, `agentic_rails_memory`). If an artifact needs no install/uninstall behavior, it is not a plugin.
