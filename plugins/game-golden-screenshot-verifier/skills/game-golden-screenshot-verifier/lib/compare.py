"""Golden-screenshot similarity metric.

Reproduces the Block Game 2 engine's ImageHelper.CompareImages / Test_ImageWithin
math so a generalized, engine-independent eval yields the same numbers the origin
harness did:

    per_pixel_diff = |dR| + |dG| + |dB| + |dA|     # 0..1020 for 8-bit RGBA
    mean_abs_diff  = mean(per_pixel_diff)          # 0..1020, averaged over pixels
    accuracy       = 1 - mean_abs_diff / 10        # 1.0 == identical
    percent        = accuracy * 100                # compared against the threshold

Identical images score 100. A mean per-pixel RGBA drift of 0.5 units scores 95,
matching the origin's documented behavior. This module has no GUI dependencies so
the metric can be tested headlessly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ImageInput = str | Path | Image.Image


def _load_rgba(image: ImageInput) -> Image.Image:
    loaded = image if isinstance(image, Image.Image) else Image.open(image)
    return loaded.convert("RGBA")


def image_similarity_pct(a: ImageInput, b: ImageInput) -> float:
    """Return similarity of two images as a percentage in [0, 100].

    Raises ValueError if the images differ in size — the origin comparison threw
    in that case, and a size mismatch means the capture pipeline changed, which
    should surface as a hard failure rather than a silent low score.
    """
    image_a = _load_rgba(a)
    image_b = _load_rgba(b)
    if image_a.size != image_b.size:
        raise ValueError(
            f"image size mismatch: {image_a.size} vs {image_b.size} "
            "(capture must produce the same dimensions as the golden)"
        )

    array_a = np.asarray(image_a, dtype=np.int16)
    array_b = np.asarray(image_b, dtype=np.int16)
    per_pixel_diff = np.abs(array_a - array_b).sum(axis=2)  # 0..1020 per pixel
    mean_abs_diff = float(per_pixel_diff.mean())
    percent = (1.0 - mean_abs_diff / 10.0) * 100.0
    return max(0.0, min(100.0, percent))
