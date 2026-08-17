---
name: agentic-rails-marketplace-design
description: Design and purpose document for the agentic_rails_marketplace repository — the source of truth and native plugin marketplace for installable lifecycle guardrails served to Claude Code, Codex, and Cursor.
metadata:
  version: "0.4"
  status: "Draft for review"
  owner: "Jarryd Adaens"
  repo: "agentic_rails_marketplace"
---

# agentic_rails_marketplace — Design Specification

## Purpose of This File

This document defines what the `agentic_rails_marketplace` repository is, why it
exists as a separate repository, how it fits alongside the other Agentic Rails
repositories, and how it is meant to be used. It is written to be read first by
a Claude Code instance tasked with reviewing and setting the repository up. It
deliberately records the reasoning and the boundaries, not just the mechanics,
because the boundaries are the point.

---

## 1. What This Repository Is

`agentic_rails_marketplace` is a **native plugin marketplace**. It is a git
repository that Claude Code, Codex, and Cursor can register as a marketplace, and
from which each tool can natively install, update, enable, disable, and remove
individual plugins.

The plugins it holds are **installable, lifecycle-managed agentic artefacts**:
evaluations, guardrails, and the hooks that wire them into a tool. These are the
artefacts that are *not* inert files — they register into a tool's hook system
and therefore need real install-and-uninstall behaviour, not just file copying.

In one sentence:

> This repository is the source of truth for agentic artefacts that have a
> lifecycle, distributed through each IDE's own native marketplace mechanism
> rather than through file deployment.

### Vocabulary

- **Marketplace** — this whole repository. The thing a tool "adds". It is the
  vendors' own term for this layer, chosen deliberately so the name matches what
  a user literally types when registering it. One owner, many plugins.
- **Plugin** — one independently installable unit inside the marketplace. The
  unit of independent install-and-remove.
- **Payload** — the inert files a plugin carries (hook scripts, agent
  definitions, eval logic).
- **Registration** — the tool-specific manifest entry that makes a payload
  active (e.g. a Claude `settings.json`/plugin entry, a Codex `config.toml`
  entry).

---

## 2. Why It Exists (and Why It Is Separate)

The Agentic Rails system already has repositories for inert artefacts — a
context starter, the agentic tooling that Kung Fu deploys, and a memories
repository. Those all share one property: their contents are **inert files**.
They are deployed by one-way file copy (Kung Fu's job), with no install logic,
no config merge, and no uninstall.

Evaluations and guardrails are different **in kind**. They wire into a tool's
hooks to function. That means they need:

- installation that registers hooks into live tool config,
- **removal** when a guardrail is renamed, superseded, or no longer wanted,
- versioning and update,
- enable/disable without full uninstall,
- cleanup of stale registrations.

That list is a **package lifecycle**. Building and maintaining a lifecycle
engine over other tools' constantly-changing config formats is a maintenance
trap: it means permanently chasing vendor changes and reimplementing, badly,
what each vendor already ships. The decisive realisation behind this repository
is that **the native marketplaces already solve exactly the hard parts** —
uninstall, versioning, enable/disable, stale-cleanup — and keep them current
because that is the vendor's job.

So the separation is drawn on a real, stable property, not on convenience:

| Property | Repositories | Delivery mechanism |
| --- | --- | --- |
| Inert files, no lifecycle | context starter, agentic tooling, memories | **Push** — Kung Fu copies them, one-way |
| Lifecycle (install/uninstall, hooks, config merge) | **`agentic_rails_marketplace`** | **Pull** — native marketplaces, each tool fetches |

This repository is the fourth repository because it lives on the other side of
the **lifecycle line**. It is not a fourth bucket next to the other three; it is
a different *type* of thing, distributed by a different machine.

### The boundary rule (do not erode this)

> Kung Fu must not manage this repository. The moment a copier starts installing
> hook-wired artefacts, it inherits install-without-uninstall and the whole
> package-manager trap reopens. Everything in this repository goes through the
> native marketplaces, full stop.

The name of the repository was chosen to help enforce this: it is literally
called a marketplace, so its delivery mechanism is self-evident.

---

## 3. How It Relates to the Other Repositories

```text
Agentic Rails system
│
├── context starter        ─┐
├── agentic tooling         ├─ inert files · PUSH · deployed by Kung Fu (one-way copy)
├── memories               ─┘
│
└── agentic_rails_marketplace ── lifecycle artefacts · PULL · native marketplaces
                                  (Claude Code + Codex + Cursor install/remove natively)
```

- The first three repositories keep their existing discipline and Kung Fu keeps
  deploying them unchanged. Most artefacts (agents, rules, skills, memories) stay
  here — they are folder-drops and this is Kung Fu's sweet spot.
- This repository is consumed by each tool's own marketplace commands. Kung Fu
  is **not** in the loop for these artefacts.
- Same source-of-truth discipline across all four repositories; two different
  delivery machines because there are two different kinds of payload.

Cross-references for the reviewing agent to pull in during setup:

- **Kung Fu `design.md`** — the source-first / one-way / managed-folder safety
  model, and specifically the OpenCode guarded-config-overwrite precedent, which
  is the reference pattern for *why* config-merging lifecycle work was kept out
  of Kung Fu.
- **Kung Fu plugin-management proposal** — the proposal that was evaluated and
  deliberately **not** built into Kung Fu; this repository is the alternative
  conclusion that came out of that evaluation.
- **Agentic tooling repo** — where evaluations and guardrails currently live
  before extraction into this repository.

---

## 4. Repository Layout (three host roots plus the pi root, one marketplace)

Claude Code, Codex, and Cursor are structurally similar but **not**
interchangeable: they use different manifests, hook event names, response
schemas, install paths, and CLIs — and they evolve independently, on their own
release cadence. This repository carries three separate source roots,
`plugins/claude/`, `plugins/codex/`, and `plugins/cursor/`, each holding only
the plugins that host supports, with a single host manifest and no runtime
host-detection branching. A plugin that serves more than one host exists as an
independent copy in each host's root; there is no shared-payload folder.

A fourth source root, `plugins/pi/`, exists for the fourth host, Pi. It is
structurally unlike the other three and is **not** a fourth peer of them —
see the key points below before reshaping anything under it.

```text
agentic_rails_marketplace/
├── README.md                         # short pointer to this design doc
├── context/design.md                 # this file
│
├── .claude-plugin/
│   └── marketplace.json              # Claude catalog — lists plugins/claude/* only
│
├── .agents/
│   └── plugins/
│       └── marketplace.json          # Codex catalog — lists plugins/codex/* only
│
├── .cursor-plugin/
│   └── marketplace.json              # Cursor catalog — lists plugins/cursor/* only
│
├── package.json                      # the one pi package manifest — the whole repository
│                                     # is a single pi package, not one package per guardrail
│
└── plugins/
    ├── claude/
    │   └── <plugin-name>/            # single-host plugin: one manifest, no branching
    │       ├── hooks/ · mcp/ · agents/
    │       └── .claude-plugin/
    ├── codex/
    │   └── <plugin-name>/
    │       ├── hooks/ · mcp/ · agents/
    │       └── .codex-plugin/
    ├── cursor/
    │   └── <plugin-name>/
    │       ├── hooks/ · mcp/ · agents/
    │       └── .cursor-plugin/
    └── pi/                           # NOT a fourth peer — no manifests, no catalog
        ├── shared/                   # library imported by the extensions; not loaded as one
        └── <guardrail-name>/         # plain source folder, reached by the root package glob
            ├── extensions/<guardrail-name>.ts
            ├── tests/
            └── README.md
```

Key points:

- Each host root is a closed world: its catalog resolves entirely inside
  `plugins/<host>/`, and every plugin folder there carries exactly one host
  manifest. No plugin folder anywhere contains more than one `.*-plugin/`
  directory — and no `.*-plugin/` directory may appear under `plugins/pi/`
  at all, because Pi has no manifest concept.
- A plugin available on more than one host is duplicated once per host root,
  not shared. The duplication is deliberate: it lets a change to one host's
  payload land without touching the others, and it lets each copy be pruned to
  exactly the branching that host needs — usually none, since a single-host
  copy has nothing left to detect.
- The three top-level `marketplace.json` files are the catalogs each tool
  reads to discover what plugins exist; each lists only its own host's plugins,
  under `./plugins/<host>/<name>`.
- **`plugins/pi/` is not a fourth peer of the three host roots.** Pi has no
  per-plugin manifest and no marketplace catalog — there is nothing to list
  and nothing to register. The root `package.json` declares the **whole
  repository as one pi package**, with an `extensions` glob
  (`plugins/pi/*/extensions/*.ts`) that reaches into each guardrail folder.
  The guardrail folders there are plain source folders, not installable units,
  and `plugins/pi/shared/` is a library they import — deliberately kept out of
  the glob by the glob's `/extensions/` segment. Granularity on Pi comes from
  `pi config` resource filtering over the one installed package, not from
  install-and-remove of individual folders (see §5).
- Cross-tree drift (a fix landing in one host's copy and not its siblings) is
  the risk this layout accepts in exchange for host isolation. It is caught by
  a root-level structural and behavioral test suite that walks all three roots,
  not by keeping the payload physically shared.
- Everything is **plain files and folders** — diffable, reviewable, copyable.
  Do **not** store payloads as zip archives; zips defeat diffing, review, and
  native fetch, and force an unzip step nothing else needs.

---

## 5. Plugin Granularity and Naming

### Granularity: the unit of a plugin is the unit of independent install-and-remove

- If two evals are always used together, or one depends on the other, they are
  **one** plugin. Splitting them would only create a way to install a broken
  half.
- If they are useful apart, they are **separate** plugins.
- The test is **shared lifecycle / interdependence**, not topic similarity.

This granularity is the payoff of the whole approach: a machine installs only
the plugins that fit the work it does. A video-game evaluation and a
web-browser-test evaluation are separate plugins, and a given machine installs
whichever is relevant and leaves the other uninstalled.

### This does not hold on Pi (recorded departure)

Recorded plainly, because the section's opening claim is otherwise the design's
load-bearing one: **"a plugin is the unit of independent install-and-remove" is
false on the Pi host, and Pi alone breaks it.**

Why it cannot hold: a Pi git source clones the repository **from its root with
no subdirectory selector** — `git:host/user/repo@ref` is the entire addressing
scheme; there is no `#path/to/subdir` syntax. A multi-guardrail repository
cannot expose per-guardrail git installs at all. Local paths *can* be installed
per folder, but a local install is machine-bound (Pi records the path in
`settings.json` relative to the settings file where it can) and is a
development convenience, not a distribution. One repository per guardrail
would restore the granularity, at the cost of splitting this repository apart
— rejected.

What delivers the granularity instead: one `pi install` of the repository,
then `pi config` resource filtering (the settings `packages` array supports
per-resource globs, exclusions, and force-include/force-exclude) to enable or
disable individual guardrails without reinstalling. The test for *what belongs
together* — shared lifecycle / interdependence — is unchanged; only the
*mechanism* that separates the rest differs on this host.

What would have to change in Pi to reverse the decision, as of the verified
pi 0.84.2: git-source addressing with a subdirectory selector — or recognition
of a subdirectory's own `package.json` as a distinct, independently
installable package inside a cloned repository — giving each guardrail folder
its own install/update/remove identity without forking the repository. No such
mechanism exists as of 16 August 2026 (`context/pi-agentic-ide/pi-agentic-ide.md`
§6 and §9.10).

### Naming convention (decide early, painful to change later)

Once there are dozens of plugins across domains, names must sort and filter
sensibly in each tool's plugin browser. Adopt a **domain-then-purpose**
convention so related plugins cluster (e.g. game-* together, web-* together).
Settle this before the list grows, because renaming across two marketplace
formats later is costly.

*(The concrete convention is left for the setup discussion; the requirement is
that one is chosen and applied consistently across both manifest formats.)*

---

## 6. How It Is Used

### Publishing (owner side)

1. Author or extract an eval/guardrail as a plugin under `plugins/<host>/<name>/`,
   once per host that supports it.
2. Add that host's own manifest (`.claude-plugin/plugin.json`,
   `.codex-plugin/plugin.json`, or `.cursor-plugin/plugin.json`) inside each copy.
3. Register the plugin in that host's own `marketplace.json` catalogue.
4. Commit and push. The repository *is* the source of truth; commit history is
   the version record.

### Consuming (per machine, per tool)

1. **Add the marketplace once** in each tool, pointed at this repository.
2. **Install individual plugins** as needed for the work that machine does.
3. **Update / enable / disable / remove** using each tool's native marketplace
   commands. This is the lifecycle behaviour that justified making this a
   marketplace rather than a Kung Fu category.

### Private-repository access

This repository can stay **private**. Both tools install from git and rely on
existing git credentials, so a machine that is authenticated to reach the repo
can install from it.

Caveat to verify at setup time (§7): Claude Code's private-marketplace
credential handling has been reported as unreliable, with a known workaround of
cloning the repo locally and registering it as a local path. Codex's git-backed
auth appears cleaner. A local clone is also diffable and instant to update,
which suits an early experimentation phase.

---

## 7. Setup Tasks and Open Questions for the Reviewing Agent

The reviewing Claude instance should treat the following as **verification and
setup work**, confirming against **current** vendor documentation (both plugin
systems are new and their paths/commands move):

1. **Confirm the exact Claude marketplace layout** — filename, location, and
   `marketplace.json` schema for the registry, and `plugin.json` schema for each
   plugin. Validate the proposed `.claude-plugin/` structure against it.
2. **Confirm the exact Codex marketplace layout** — personal vs repo marketplace
   file location (`.agents/plugins/marketplace.json` and related), plugin
   manifest location (`.codex-plugin/plugin.json`), cache and enabled-state
   locations. Validate the proposed `.codex-plugin/` structure.
3. **Confirm private-repo install** for both tools, and capture the Claude
   local-clone workaround steps if the direct private add misbehaves.
4. **Confirm hook trust behaviour** — both tools treat hooks as high-trust and
   may require explicit review/trust before hooks run. Document what the user
   must approve on install.
5. **Confirm graceful degradation** — verify that an unresolved/half-configured
   plugin entry is skipped rather than breaking the whole marketplace.
6. **Decide the plugin naming convention** (§5) and apply it across both
   manifest formats.

### Non-goals (explicitly out of scope)

- This repository does **not** manage individual coding projects.
- Kung Fu does **not** deploy, copy, or otherwise manage this repository.
- This repository does **not** implement its own install/uninstall/version
  engine. That is delegated to the native marketplaces by design.

---

## 8. Design Principles (summary)

- **Lifecycle line:** inert files are pushed by Kung Fu; lifecycle artefacts are
  pulled by native marketplaces. This repository is on the pull side.
- **Use the package manager that exists:** when a feature's next logical step is
  a package manager (uninstall, rename-cleanup, freeze, reconcile), use the one
  the tools already ship rather than building one.
- **Name things after what the target system calls them:** "marketplace",
  "plugin" — vendor vocabulary, no invented metaphors.
- **Plain files, not archives:** everything diffable, reviewable, natively
  fetchable.
- **One host, one copy, one manifest:** each host root carries its own payload
  and its own manifest; no cross-host branching, no shared-payload folder.
- **Granularity follows lifecycle:** a plugin is the unit of independent
  install-and-remove.
