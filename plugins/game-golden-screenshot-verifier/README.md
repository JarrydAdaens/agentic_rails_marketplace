# game-golden-screenshot-verifier

Engine-independent runtime smoke verifier for games, delivered as a
marketplace plugin. It answers "does the game still boot and render
correctly?" by launching the game, driving it into a deterministic state,
capturing a screenshot from the outside, and comparing it against a
human-approved golden image versioned in the target project. Exit code `0` =
pass, `1` = fail.

The whole payload is one skill, `game-golden-screenshot-verifier`, which
carries the runner and its libraries and documents setup and usage — see
`skills/game-golden-screenshot-verifier/SKILL.md`. Works in both Claude Code
and Codex (skills only, no hooks).

## Division of ownership

| Lives in the plugin (updated via marketplace) | Lives in the target project (the seam) |
| --- | --- |
| `run_eval.py` — launch, drive, capture, compare, verdict | `eval_config.json` — the game-specific knobs |
| `lib/` — capture, comparison metric, config loading | `drivers/<your-driver>.py` — the deterministic-state route |
| `drivers/input_stub.py` — the driver template to copy out | `goldens/` — committed reference screenshots |
| `tests/test_compare.py` — metric lock-down tests | `last-run/` — git-ignored per-run artifacts |

The runner executes from the plugin cache and resolves every project path
(config-relative), so plugin updates never touch a project's goldens, config,
or driver.

## What is preserved from the origin (the hard-won part)

- **Golden mode vs eval mode**, with goldens versioned and reviewed by eye.
- **A launch timeout** that kills a hung game.
- **"Couldn't capture" always counts as failure** — a crash or early exit is a
  hard fail, never a silent pass.
- **Every run's artifacts land in `last-run/`** for inspection.
- The similarity metric reproduces the origin engine's formula
  (`accuracy = 1 − meanAbsDiff/10`) so thresholds carry over.

## Requirements

Python 3.10+ and [`uv`](https://docs.astral.sh/uv/); dependencies (Pillow,
NumPy, mss, PyGetWindow, PyAutoGUI) are declared inline in `run_eval.py` and
install automatically on first `uv run`. Screen capture and input injection
are OS-level, so runs need a real desktop session (Windows-first; the
libraries also support macOS/Linux).

## Provenance

Generalized from the Block Game 2 / Craft World autotest eval, previously
maintained as a drop-in verifier in `agentic_rails_tooling` and extracted here
as a plugin (v2.0: project paths now resolve against the config file rather
than the runner's folder).
