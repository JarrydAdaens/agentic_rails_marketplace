"""Screenshot capture — the engine-independent replacement for Test_PrtScn.

The origin harness rendered the 3D scene to an offscreen target inside the game.
Here we capture from the outside using OS-level screen grab, so the eval works
against any game executable without engine cooperation. GUI/OS dependencies are
imported lazily so the similarity metric in compare.py stays headlessly testable.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _window_bbox(title: str) -> dict:
    """Resolve a window title substring to an {left, top, width, height} box."""
    import pygetwindow as gw

    matches = [w for w in gw.getWindowsWithTitle(title) if w.width > 0 and w.height > 0]
    if not matches:
        raise RuntimeError(
            f"no visible window matching title '{title}'. The game may have failed "
            "to open a window, or window_title in the config is wrong."
        )
    window = matches[0]
    return {"left": window.left, "top": window.top, "width": window.width, "height": window.height}


def _grab(bbox: dict | None) -> Image.Image:
    """Grab a screen region (or the primary monitor when bbox is None) as RGBA."""
    import mss

    with mss.mss() as sct:
        monitor = bbox if bbox is not None else sct.monitors[1]
        shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.rgb).convert("RGBA")


def capture(
    out_path: Path,
    mode: str = "window",
    window_title: str = "",
    region: list[int] | None = None,
    size: list[int] | None = None,
) -> Image.Image:
    """Capture the game view and write it to out_path as PNG.

    Resizing to size keeps goldens window- and resolution-independent, mirroring
    the origin's fixed-size render target. Returns the saved image.
    """
    if mode == "region":
        if not region or len(region) != 4:
            raise ValueError("region capture requires [x, y, w, h]")
        x, y, w, h = region
        bbox = {"left": x, "top": y, "width": w, "height": h}
    elif mode == "window":
        bbox = _window_bbox(window_title)
    else:  # fullscreen
        bbox = None

    image = _grab(bbox)
    if size:
        image = image.resize((int(size[0]), int(size[1])), Image.LANCZOS)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return image
