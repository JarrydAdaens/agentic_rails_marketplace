# agentic_rails_marketplace

The native lifecycle-guardrail marketplace for Agentic Rails. It is directly
registerable by Claude Code, Codex, and Cursor; Kung Fu does not copy or deploy
anything from this repository.

## Registering

```shell
# Claude Code or Codex interactive command
/plugin marketplace add <git-url-or-local-path-to-this-repo>

# Cursor CLI (Git URL)
agent plugin marketplace add <git-url-to-this-repo>
```

Registering a Cursor marketplace does **not** install every catalog entry, and
adding an `enabled: true` entry to `.cursor/settings.json` is not an install.
Install each plugin through Cursor's interactive `/plugin` Marketplace screen
or **Customize → Marketplace**, choose project or user scope, approve its MCP
server, then start a fresh session. During local development, load one plugin
with `agent --plugin-dir <plugin-path>`.

## Plugins

| Plugin | Hosts | Purpose |
| --- | --- | --- |
| `local-advisor-guardrail` | Claude Code, Codex, Cursor | Requires a read-only child agent within the current IDE before the first session write. Uses Opus High, GPT-5.6 Sol High, or Cursor Grok 4.5 High according to the host. |
| `jobs-done-guardrail` | Claude Code, Cursor | Runs configured build and test gates at completion and requests bounded repairs on failure. |
| `codex-as-advisor-guardrail` | Claude Code, Cursor | Requires constructive GPT-5.6 Sol High advice before writing. |
| `codex-as-critic-guardrail` | Claude Code, Cursor | Requires an antagonistic GPT-5.6 Sol High review before writing. |
| `claude-as-advisor-guardrail` | Codex, Cursor | Requires constructive advice from the latest Claude Opus alias at high effort before writing. |
| `claude-as-critic-guardrail` | Codex, Cursor | Requires an antagonistic review from the latest Claude Opus alias at high effort before writing. |
| `cursor-as-advisor-guardrail` | Claude Code, Codex | Configurable advisor backed by Cursor Grok 4.6 High at standard speed. |
| `cursor-as-critic-guardrail` | Claude Code, Codex | Requires an antagonistic Cursor Grok 4.6 High review at standard speed before writing. |
| `python-uv-guardrail` | Claude Code, Cursor | Blocks direct Python/pip commands in favor of uv. |
| `readme-name-guardrail` | Claude Code, Cursor | Reserves README.md for the project root. |

Technology-specific WPF and game screenshot checks live in
`jarryds-agent-marketplace`, which is deliberately opinionated about stacks.

## Layout

```text
.claude-plugin/marketplace.json    # Claude Code catalog
.agents/plugins/marketplace.json   # Codex catalog
.cursor-plugin/marketplace.json    # Cursor catalog
plugins/<plugin-name>/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json      # when Codex-compatible
├── .cursor-plugin/plugin.json     # when Cursor-compatible
├── hooks/ · mcp/ · agents/ · skills/
└── README.md
```

Host manifests may select different hook files or MCP launch arguments, but a
portable capability keeps one stable plugin name and one shared protocol.
Each lead can choose either role from either independent provider. Existing
same-IDE child-agent options remain available where useful. Installing multiple
consultation guardrails intentionally creates multiple first-write gates.

## Publishing

1. Keep every plugin self-contained; installed copies cannot reach outside the
   plugin folder.
2. Add the compatible per-host manifests and catalog entries.
3. Use `${CLAUDE_PLUGIN_ROOT}` for Claude launchers. Cursor MCP launchers use
   `${PLUGIN_ROOT}` plus `cwd: "${PLUGIN_ROOT}"`; Cursor hook commands are
   plugin-relative because plugin hooks execute from the plugin root.
4. Cursor consultation adapters on Windows must start with an absolute native
   executable, restore user and machine PATH values from the registry, and
   resolve UV plus child-agent CLI shims without operator environment changes.
5. Validate with `claude plugin validate .`, test host adapters, and confirm
   every catalog source resolves before committing.

This repository is licensed under the [Apache License 2.0](LICENSE).
