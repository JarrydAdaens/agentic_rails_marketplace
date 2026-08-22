# rails-marketplace-surgeon

Cursor-only experimental repair for stale `agentic-rails` marketplace/plugin
cache payloads. It is the mutating companion to `rails-marketplace-doctor`.

## Commands

- `/rails-marketplace-surgeon` — inspect the proposed repair and request an
  explicit apply decision.
- `/rails-surgeon-health` — inspect whether the local cache representation is
  repairable and whether the marketplace checkout is current.
- `/rails-surgeon-help` — explain mutation boundaries and limitations.

## Mutation policy

Surgeon only mutates after its runner receives `--apply`. It never creates
backup directories, rollback journals, or persistent recovery artefacts. It
updates the marketplace checkout, creates current-commit cache payloads for
stale installed plugins, and preserves plugin-owned configuration by never
touching locations outside Cursor's marketplace/cache trees.

Cursor does not document every local pin/index representation. Surgeon verifies
the filesystem representation it can observe, but cannot promise that Cursor's
account-backed selection state will choose a newly created cache payload. Always
run `/rails-marketplace-doctor` afterwards; that is the independent verifier.
