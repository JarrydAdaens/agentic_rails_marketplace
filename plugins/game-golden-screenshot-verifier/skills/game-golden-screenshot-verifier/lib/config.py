"""Load and validate the per-game eval configuration.

The config is the one piece every consuming project must fill in. It keeps the
game-specific knobs (executable, launch arguments, which window to capture,
threshold, timings, and which input driver reaches the deterministic state) out
of the runner so the runner itself stays engine-agnostic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CaptureConfig:
    mode: str = "window"                    # "window" | "region" | "fullscreen"
    region: list[int] | None = None         # [x, y, w, h], used when mode == "region"
    size: list[int] | None = None           # [w, h] to resize the capture to before comparing


@dataclass
class EvalConfig:
    executable: str
    window_title: str = ""
    working_dir: str | None = None
    launch_args: list[str] = field(default_factory=list)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    threshold: float = 95.0
    timeout_sec: int = 240
    warmup_sec: float = 15.0                 # wait after launch for the game to reach a driveable state
    settle_sec: float = 2.0                  # wait after driving input before capturing
    driver: str = "drivers/input_stub.py"    # module that reaches the deterministic scene, relative to the config file's folder
    golden_name: str = "golden.png"


def load_config(path: Path) -> EvalConfig:
    """Read and validate an eval config JSON file."""
    if not path.is_file():
        raise FileNotFoundError(
            f"config not found at '{path}'. Copy eval_config.example.json and edit it."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))

    if "executable" not in raw or not str(raw["executable"]).strip():
        raise ValueError("config is missing required 'executable' path")

    capture_raw = raw.get("capture", {}) or {}
    capture = CaptureConfig(
        mode=capture_raw.get("mode", "window"),
        region=capture_raw.get("region"),
        size=capture_raw.get("size"),
    )
    if capture.mode not in ("window", "region", "fullscreen"):
        raise ValueError(f"capture.mode must be window|region|fullscreen, got '{capture.mode}'")
    if capture.mode == "region" and (not capture.region or len(capture.region) != 4):
        raise ValueError("capture.mode 'region' requires capture.region = [x, y, w, h]")

    return EvalConfig(
        executable=raw["executable"],
        window_title=raw.get("window_title", ""),
        working_dir=raw.get("working_dir"),
        launch_args=list(raw.get("launch_args", [])),
        capture=capture,
        threshold=float(raw.get("threshold", 95.0)),
        timeout_sec=int(raw.get("timeout_sec", 240)),
        warmup_sec=float(raw.get("warmup_sec", 15.0)),
        settle_sec=float(raw.get("settle_sec", 2.0)),
        driver=raw.get("driver", "drivers/input_stub.py"),
        golden_name=raw.get("golden_name", "golden.png"),
    )
