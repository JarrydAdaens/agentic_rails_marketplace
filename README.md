# agentic_rails_marketplace

The native lifecycle-guardrail marketplace for Agentic Rails. It is directly
registerable by Claude Code, Codex, and Cursor and installable by Pi as a
single package; Kung Fu does not copy or deploy anything from this
repository.

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

## Pi

Pi has no marketplace: there is nothing to register and no catalog to add, so
Pi never uses `/plugin marketplace add`. The whole repository is **one pi
package** (declared by the root `package.json`), and Pi installs it with
`pi install`:

```shell
pi install git:github.com/JarrydAdaens/agentic_rails_marketplace   # portable install
pi install <local-path-to-this-repo>                                 # development convenience
```

One install makes all seven Pi guardrails available. Pi cannot install a
subdirectory of a repository — a git source clones from the repository root
with no subdirectory selector — so individual guardrails are enabled and
disabled with `pi config`, not installed and removed individually.

A local-path install is machine-bound: pi may record the path in
`~/.pi/agent/settings.json` **relative to the settings file itself**, so a
settings file copied to another machine resolves the path somewhere
unintended. Use the git URL for the supported install and the local path only
for development.

## Plugins

| Plugin | Hosts | Purpose |
| --- | --- | --- |
| `local-advisor-guardrail` | Claude Code, Codex, Cursor | Requires a read-only child agent within the current IDE before the first session write. Uses Opus High, GPT-5.6 Sol High, or Cursor Grok 4.5 High according to the host. |
| `jobs-done-guardrail` | Claude Code, Cursor | Runs configured build and test gates at completion and requests bounded repairs on failure. |
| `codex-as-advisor-guardrail` | Claude Code, Cursor, Pi | Requires constructive GPT-5.6 Sol High advice before writing. Pi host: the consult path is unverified (Codex quota exhausted); the gate-disarm path is tested. |
| `codex-as-critic-guardrail` | Claude Code, Cursor | Requires an antagonistic GPT-5.6 Sol High review before writing. |
| `claude-as-advisor-guardrail` | Codex, Cursor, Pi | Requires constructive advice from the latest Claude Opus alias at high effort before writing. |
| `claude-as-critic-guardrail` | Codex, Cursor | Requires an antagonistic review from the latest Claude Opus alias at high effort before writing. |
| `claude-as-review-bot-guardrail` | Pi | At session wrap-up, an external read-only Claude Opus session approves or rejects the session's changes and returns bounded remediation. Does not run under `pi -p` (it stands down there). |
| `cursor-as-advisor-guardrail` | Claude Code, Codex, Pi | Configurable advisor backed by Cursor Grok 4.6 High at standard speed. |
| `cursor-as-critic-guardrail` | Claude Code, Codex | Requires an antagonistic Cursor Grok 4.6 High review at standard speed before writing. |
| `python-uv-guardrail` | Claude Code, Cursor, Pi | Blocks direct Python/pip commands in favor of uv. |
| `readme-name-guardrail` | Claude Code, Cursor, Pi | Reserves README.md for the project root. |
| `git-push-guardrail` | Pi | Blocks `git push` for the agent, terminating the run — there is no remedy the agent may reach. |

Technology-specific WPF and game screenshot checks live in
`jarryds-agent-marketplace`, which is deliberately opinionated about stacks.

## Layout

```text
.claude-plugin/marketplace.json    # Claude Code catalog
.agents/plugins/marketplace.json   # Codex catalog
.cursor-plugin/marketplace.json    # Cursor catalog
package.json                       # the one pi package manifest for the whole repository
plugins/<host>/<plugin-name>/      # one folder per plugin per host root (claude, codex, cursor)
├── .claude-plugin/plugin.json     # exactly one host manifest, matching its root
├── hooks/ · mcp/ · agents/ · skills/
└── README.md
plugins/pi/<guardrail-name>/       # pi root — structurally different, see below
├── extensions/<guardrail-name>.ts
└── README.md
plugins/pi/shared/                 # library imported by the pi extensions; not itself loaded
```

Host manifests may select different hook files or MCP launch arguments, but a
portable capability keeps one stable plugin name and one shared protocol.
Each lead can choose either role from either independent provider. Existing
same-IDE child-agent options remain available where useful. Installing multiple
consultation guardrails intentionally creates multiple first-write gates.

`plugins/pi/` is **not a fourth peer** of the three host roots. It has no
per-plugin manifest and no catalog: the repository root's `package.json`
declares the entire repository as a single pi package whose extension glob
reaches into `plugins/pi/*/extensions/*.ts`. Granularity on Pi comes from
`pi config` filtering, not from install-and-remove. See `context/design.md`
§4 and §5.

## Known limitations

- **The Codex advisor's consult path is UNVERIFIED.** The Codex quota on the
  development machine is exhausted, so a live consult could not be run; the
  command line is verified and the gate-disarm path is tested. Re-verify when
  quota returns.
- **The review bot does not work under `pi -p`.** In print mode the session
  exits before an injected message can run, so the guardrail stands down
  silently; there is no review, by design.
- **A denied write can be routed around with a shell redirect through the
  `bash` tool** (`>`, `>>`, `tee`). Every host in this repository shares that
gap — the gates watch the structured write tools, not shell redirects. It was
measured on Pi: the local model did it unprompted, within one turn, after a
clean denial of the `write` tool. Closing it means extending the advisor gates
to redirect-carrying `bash` segments on all hosts, which is a separate story.

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
5. Validate with `claude plugin validate .`, run the Python suite
   (`uvx --with pytest pytest tests/ -q`) and the pi behavioral tests
   (`"C:\Users\Jarry\AppData\Local\pi-node\current\node.exe" --test
   "plugins/pi/**/*.test.ts"`), test host adapters, and confirm every catalog
   source resolves before committing.

This repository is licensed under the [Apache License 2.0](LICENSE).
