# Setting the Cursor advisor model

How to point the `cursor-as-advisor-guardrail` plugin's advisor at a specific
Cursor model — worked through with **Cursor Grok 4.6 at high reasoning, not the
Fast variant**.

This document is self-contained. It is meant to be handed to an agent working
on a machine that has the plugin installed, and it assumes nothing beyond a
signed-in Cursor Agent CLI.

## The short answer

The model ID you want is:

```text
cursor-grok-4.6-high
```

This is also the plugin's built-in default, so a project with no configuration
is already on it. To pin the choice explicitly — or to move a project that was
previously set to something else — create this file in the **root of the
project you are working in**:

```text
harness/cursor-as-advisor-guardrail/cursor-config.json
```

with exactly this content:

```json
{
  "default_model": "cursor-grok-4.6-high"
}
```

Every `consult_advisor` call from that project now runs on Cursor Grok 4.6 at
high reasoning. Nothing else needs changing — no plugin edit, no environment
variable, no Claude Code setting.

## Why that exact ID

`agent models` lists the Grok family as separate IDs, one per reasoning level,
with a distinct `-fast` sibling for each:

| ID | Display name | Use it? |
| --- | --- | --- |
| `cursor-grok-4.6-high` | Cursor Grok 4.6 | **Yes** — high reasoning, not Fast |
| `cursor-grok-4.6-high-fast` | Cursor Grok 4.6 Fast | No — this is the Fast variant |
| `cursor-grok-4.6-medium` / `-medium-fast` | Cursor Grok 4.6 Medium | No — lower reasoning |
| `cursor-grok-4.6-low` / `-low-fast` | Cursor Grok 4.6 Low | No — lower reasoning |

Reasoning effort and Fast-versus-standard are **encoded in the ID itself**.
There is no separate effort setting to turn up and no Fast toggle to turn off —
picking `cursor-grok-4.6-high` is how you say "high reasoning, standard speed".

Model IDs are account- and version-dependent. Confirm the ID exists on the
machine before relying on it:

```powershell
agent models
```

Look for the line `cursor-grok-4.6-high - Cursor Grok 4.6`. If the Grok IDs are
absent or spelled differently in that listing, use what the listing actually
says — it is the only authority.

## How the plugin picks a model

Resolution order, highest priority first:

1. The optional `model` argument on a single `consult_advisor` call.
2. `default_model` in `harness/cursor-as-advisor-guardrail/cursor-config.json`, read
   from the project root (`CLAUDE_PROJECT_DIR`, otherwise the working
   directory).
3. The plugin's built-in fallback, `cursor-grok-4.6-high`, when no config file
   exists.

Because the built-in fallback is already Cursor Grok 4.6 at high reasoning, a
project that wants exactly that needs **no config file at all**. Write the file
anyway when you want the choice pinned and visible in the repository, or when
you want a different model.

Two consequences worth internalizing:

- **The setting is per project, not per machine or per user.** There is no
  global or user-level model setting. Every repository you want on Grok needs
  its own `harness/cursor-as-advisor-guardrail/cursor-config.json`.
- **A successful call with an explicit `model` writes that model into the
  config file**, creating it if absent. So the one-shot path below doubles as a
  way to set the default.

## Two ways to set it

### A. Write the config file (recommended)

Deterministic, reviewable, works before any consult has happened. Create the
file shown in "The short answer". It is ordinary JSON — hand-edit it any time to
switch models.

### B. Pass `model` on one consult

Call `consult_advisor` with the usual five fields plus:

```json
"model": "cursor-grok-4.6-high"
```

If the call succeeds, the plugin remembers `cursor-grok-4.6-high` as this
project's default and later calls may omit `model`. A **failed** model selection
is not persisted.

## Verifying it worked

Two checks, both cheap:

1. Read back the config file — it should contain exactly
   `"default_model": "cursor-grok-4.6-high"`.
2. Make one consult with **no** `model` argument and set `question` to:
   *"Reply with only the name of the underlying model you are running as."*
   A correctly configured project answers `Cursor Grok 4.6`.

Both checks were run against this plugin and passed; the second is the one that
proves the config file is actually being honored rather than merely existing.

## Two traps that will bite you

**A wrong-but-accepted alias silently overwrites your config.** Passing
`model: "grok-4.6"` does *not* error. Cursor may accept it, the consult returns
normally, and the plugin would persist `"default_model": "grok-4.6"` —
after which the reasoning level and Fast-versus-standard behavior are whatever
that alias happens to map to, which is not documented and not what you asked
for. Only ever use an exact ID copied from `agent models` output.

**The parameterized bracket syntax does not work here.** `agent models` ends
its output with a tip advertising overrides like
`--model 'claude-opus-4-8[context=1m,effort=high,fast=false]'`. Passing the
equivalent Grok form, `cursor-grok-4.6[effort=high,fast=false]`, is **rejected**
— the consult fails with "model is unavailable for this account or Cursor Agent
version". Use the plain `-high` ID instead.

## Other settings, for completeness

The only environment variable the plugin reads is the consult timeout, default
600 seconds:

```jsonc
// .claude/settings.json
{ "env": { "CURSOR_ADVISOR_TIMEOUT_SECONDS": "900" } }
```

There is no environment variable for the model. Grok at high reasoning is
slower than a lightweight model such as `composer-2.5`, so if consults on a
large repository start timing out, raise this value rather than dropping to a
lower-effort model.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| "Cursor advisor model X is unavailable…" | ID not in this account's `agent models` listing, or bracket syntax used | Copy an exact ID from `agent models` |
| "Cursor authentication failed" | Not signed in | Run `agent login`, retry |
| "Cursor Agent executable 'agent' not found on PATH" | CLI not installed or not on `PATH` | Install Cursor Agent and ensure `agent` resolves in the shell that launches Claude Code |
| "config … must contain a non-empty 'default_model' string" | Config file malformed or key missing | Rewrite the file with the exact JSON above |
| Advisor answers as something other than Grok | A different model is saved in this project's config file | Read the config file and correct the ID, or delete the file to fall back to the built-in default |
| Advisor answers as Grok but feels shallow/quick | A `-fast` or lower-effort ID is saved | Read the config file and correct the ID |

## Choosing a different model

`cursor-model-ids.md`, beside this document, catalogs every model ID Cursor
currently exposes and maps informal descriptions ("the latest Grok", "Opus with
max thinking") to exact IDs. Use it whenever a human names a model loosely.
