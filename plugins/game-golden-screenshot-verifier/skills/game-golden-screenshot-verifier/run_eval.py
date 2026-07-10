# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pillow>=10",
#   "numpy>=1.24",
#   "mss>=9",
#   "pygetwindow>=0.0.9",
#   "pyautogui>=0.9.54",
# ]
# ///
"""Generalized golden-screenshot game eval.

Launch a game, drive it into a deterministic state, capture a screenshot from the
outside, and compare it against a versioned golden. Exit 0 = pass, 1 = fail.

Two modes:
  golden  Capture the current scene and store it as the new golden (review by eye,
          then commit it).
  eval    Capture the scene and assert similarity >= threshold against the golden.

This is the engine-independent generalization of the Block Game 2 autotest eval:
the hard-won verdict architecture is preserved (golden vs eval modes, versioned
goldens, a launch timeout, artifacts copied to last-run/ every run, and
"couldn't capture" always counting as failure so an early crash can never fake a
pass), while the three engine-provided pieces — scene setup, screenshot capture,
and image comparison — are replaced by an input driver, OS screen grab, and a
local diff so it runs against any executable.

The runner ships inside the agentic-rails marketplace plugin and executes from
the plugin cache; everything project-specific lives in a seam folder the target
project owns. Relative paths in the config (executable, working_dir, driver),
plus goldens/ and last-run/, all resolve against the directory containing the
config file — never against this script.

Run it with uv (dependencies install automatically):
    uv run run_eval.py --config <seam-dir>/eval_config.json            # eval mode
    uv run run_eval.py --config <seam-dir>/eval_config.json --mode golden
    uv run run_eval.py --self-test                                     # verify install + metric
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib import compare, config as config_mod  # noqa: E402


def _fail(message: str) -> int:
    print(f"EVAL FAIL: {message}", file=sys.stderr)
    return 1


def _resolve(raw_path: str, base: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (base / path)


def _load_driver(driver_path: str, base: Path):
    driver_file = _resolve(driver_path, base)
    if not driver_file.is_file():
        raise FileNotFoundError(f"driver not found at '{driver_file}'")
    spec = importlib.util.spec_from_file_location("eval_driver", driver_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "drive"):
        raise AttributeError(f"driver '{driver_file}' has no drive() function")
    return module


def _self_test() -> int:
    """Verify dependencies import and the metric behaves, without launching a game."""
    try:
        import mss  # noqa: F401
        import numpy  # noqa: F401
        import pygetwindow  # noqa: F401
        from PIL import Image
    except ImportError as error:
        return _fail(f"a dependency failed to import: {error}")

    probe = Image.new("RGBA", (16, 16), (120, 130, 140, 255))
    identical = compare.image_similarity_pct(probe, probe)
    if abs(identical - 100.0) > 1e-6:
        return _fail(f"self-test metric wrong: identical images scored {identical}, expected 100")
    print(f"Self-test OK: deps import; identical probe images score {identical:.2f}%.")
    return 0


def run(config_path: Path, mode: str) -> int:
    cfg = config_mod.load_config(config_path)
    seam_dir = config_path.resolve().parent  # the project-owned folder all relative paths anchor to

    exe = _resolve(cfg.executable, seam_dir)
    if not exe.is_file():
        return _fail(f"executable not found at '{exe}'. Build the game first, or fix 'executable' in the config.")

    goldens_dir = seam_dir / "goldens"
    last_run_dir = seam_dir / "last-run"
    golden_path = goldens_dir / cfg.golden_name
    current_path = last_run_dir / "current.png"
    goldens_dir.mkdir(parents=True, exist_ok=True)
    if last_run_dir.exists():
        shutil.rmtree(last_run_dir)
    last_run_dir.mkdir(parents=True, exist_ok=True)

    if mode == "eval" and not golden_path.is_file():
        return _fail(f"no golden at '{golden_path}'. Run with --mode golden first, eyeball it, then re-run the eval.")

    from lib import capture  # lazy: keeps the metric path free of GUI deps

    working_dir = _resolve(cfg.working_dir, seam_dir) if cfg.working_dir else exe.parent
    launch = [str(exe), *cfg.launch_args]
    print(f"Launching: {' '.join(launch)}  (timeout {cfg.timeout_sec}s)")
    deadline = time.monotonic() + cfg.timeout_sec
    proc = subprocess.Popen(launch, cwd=str(working_dir))

    try:
        # Warm up. An exit during warmup is an early crash — a hard failure, never a pass.
        if _wait_or_exit(proc, cfg.warmup_sec, deadline):
            return _fail(f"game exited during warmup (code {proc.returncode}) — crash or early death before the scene was ready.")

        try:
            _load_driver(cfg.driver, seam_dir).drive()
        except Exception as error:  # noqa: BLE001 - driver is user code; convert any fault to a fail exit
            return _fail(f"input driver '{cfg.driver}' raised: {error}")

        if _wait_or_exit(proc, cfg.settle_sec, deadline):
            return _fail(f"game exited before capture (code {proc.returncode}) — the driver may have quit it, or it crashed.")

        try:
            capture.capture(
                current_path,
                mode=cfg.capture.mode,
                window_title=cfg.window_title,
                region=cfg.capture.region,
                size=cfg.capture.size,
            )
        except (RuntimeError, ValueError, OSError) as error:
            return _fail(f"screenshot capture failed: {error}")
    finally:
        _terminate(proc)

    if mode == "golden":
        shutil.copyfile(current_path, golden_path)
        shutil.copyfile(current_path, last_run_dir / "golden.png")
        print(f"EVAL GOLDEN CAPTURED: {golden_path}")
        print("Eyeball the PNG, then run the eval without --mode golden.")
        return 0

    shutil.copyfile(golden_path, last_run_dir / "golden.png")
    try:
        similarity = compare.image_similarity_pct(golden_path, current_path)
    except ValueError as error:
        return _fail(str(error))

    print(f"Similarity: {similarity:.2f}%  (threshold {cfg.threshold:.2f}%)")
    print(f"Artifacts in: {last_run_dir}")
    if similarity < cfg.threshold:
        return _fail(f"screenshot diverged from golden ({similarity:.2f}% < {cfg.threshold:.2f}%). Compare current.png vs golden.png in last-run/.")

    print("EVAL PASS.")
    return 0


def _wait_or_exit(proc: subprocess.Popen, seconds: float, deadline: float) -> bool:
    """Sleep up to seconds (capped by the overall deadline). Return True if the process exited."""
    remaining = min(seconds, max(0.0, deadline - time.monotonic()))
    try:
        proc.wait(timeout=remaining)
        return True
    except subprocess.TimeoutExpired:
        return False


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Golden-screenshot game eval.")
    parser.add_argument("--config", type=Path, help="path to the eval config JSON")
    parser.add_argument("--mode", choices=("eval", "golden"), default="eval")
    parser.add_argument("--self-test", action="store_true",
                        help="verify dependencies and the metric without launching a game")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.config:
        parser.error("--config is required (or use --self-test)")
    return run(args.config, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
