# readme-name-guardrail (pi)

Deterministic "one README, prefixed everywhere else" guardrail for the
[Pi](https://pi.dev) coding agent. A `readme.md` (any capitalization)
anywhere but the project root piles up and crowds terminal file references,
so the codebase keeps a single, unambiguous README and every other one
carries a descriptive prefix (`creatures-readme.md`, `docs-readme.md`). The
guardrail enforces that with two `tool_call` enforcement points:

- **`write` / `edit`** — the target path must not be a forbidden readme; the
  deny names a suggested prefixed name drawn from the containing folder.
- **`bash`** — `git add` and `git commit` must not stage or commit a
  forbidden readme: the backstop for readmes created outside the agent, or
  before the plugin was installed. It handles explicit pathspecs, `-A` /
  `--all` / `-u` / `.` bulk adds, directory pathspecs, `-C <dir>` repo
  dirs, and `git commit` path arguments.

This is the pi-host sibling of `plugins/cursor/readme-name-guardrail` and
`plugins/claude/readme-name-guardrail`. They are independent
reimplementations of the same rule: the pi copy ports the *decision logic*
from `hooks/readme-guard-common.ps1` and its two callers and drops the
*transport* (stdin reading, BOM stripping, JSON envelope), which pi's
in-process hooks do not have.

## How it decides

A path is forbidden when its filename is exactly `readme.md` (any casing)
**and** its parent directory is not the project root — the root's single
README is the one allowed file. `api-readme.md`, `readme-template.md`, and
every prefixed variant are allowed anywhere.

Git commands are split into simple-command segments on the shell control
operators (shared with the other pi guardrails), and each `git add` /
`git commit` invocation is inspected on its own, so `x && git add
docs/readme.md` is caught and `git pull` is not.

Blocks with `{ block: true, reason }` and **not** `terminate`, because a
legitimate remedy exists and the deny message names it:

> readme-name-guardrail: creating 'docs/readme.md' is forbidden. The name
> 'readme.md' (any capitalization) is reserved for the single project-root
> README; extra files with that exact name pile up and crowd terminal file
> references. Give it a descriptive prefix instead - e.g. 'docs-readme.md' -
> then retry. A prefixed name like that is allowed anywhere.

The deny is the guardrail working, not an error. The behavioral tests include
the root `README.md` and the prefixed variants — the guardrail must never
block the remedy its own message recommends.

## Fail open

The handler body is wrapped so an internal guardrail error allows the
guarded tool (write, edit, or bash) through rather than blocking it. Pi's
`tool_call` fails **closed** by default — an unhandled throw wedges the
guarded tool for the session — so the wrapping is mandatory, and the
behavioral suite includes an induced-internal-error case asserting the tool
is allowed through.

## Layout

```text
readme-name-guardrail/
├── extensions/readme-name-guardrail.ts   # the pi extension (decision logic + pi glue)
├── tests/readme-name.behavior.test.ts    # behavioral tests for the deny decisions
└── README.md
```

The decision primitives it delegates to live in `plugins/pi/shared/`
(`bash-segments.ts`, `harness-config.ts`), which is importable but
deliberately not matched by the package's extension glob.

## Adopting it in a project (optional escape hatch)

The guardrail is **active by default** wherever the extension is enabled —
no seam required. The seam exists only as an escape hatch and is shared with
the Claude and Cursor hosts, so a project never grows a second config
location. To relax or disable it in a specific project, create
`harness/readme-name-guardrail/config.json` in the project root:

```json
{ "enabled": false }
```

Other supported key, mirroring the Cursor host:

```json
{
  "allowPaths": ["^generated/"]
}
```

`allowPaths` entries are regexes matched (case-insensitively) against the
repo-relative POSIX path; any match is a narrow, project-declared exception
(e.g. a docs generator's output). Absent, empty, or malformed config all
mean "enforce with defaults".

## Known limitations

- The git check relies on the working tree and `git status`/`git diff`
  queries succeeding in the repository directory; if git itself is
  unavailable, bulk adds (`-A`, `.`) are not enumerated and only explicit
  pathspecs are inspected.
- `git commit` with `-a` and staged paths are checked via
  `git diff --cached` and `git ls-files -m`; submodules and unusual index
  states are out of scope.

## Installing

Pi installs the whole repository as one package (pi has no per-plugin
catalog; granularity is via `pi config` filtering):

```text
pi install "D:/Code Projects/agentic_rails/agentic_rails_marketplace"
```

or from a git source. Then toggle this extension among the others with
`pi config`.

## Tests

```text
python tests/run_pi_behavior_tests.py
```

which runs `tests/readme-name.behavior.test.ts` (and the shared-module
tests) under pi's bundled Node with native type stripping — no dev
dependency.
