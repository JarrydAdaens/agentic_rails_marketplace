# Copyright 2026 Jarryd Adaens
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10", "numpy>=1.24"]
# ///
"""Focused tests for the similarity metric — the one piece of real logic here.

The metric reproduces a documented engine formula, so it is worth locking down:
identical images score 100, a size mismatch is a hard error, and a known drift
produces the expected percentage. Run headlessly: `uv run tests/test_compare.py`.
"""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import compare  # noqa: E402


class ImageSimilarityTests(unittest.TestCase):
    def test_identical_scores_100(self):
        image = Image.new("RGBA", (16, 16), (120, 130, 140, 255))
        self.assertEqual(compare.image_similarity_pct(image, image), 100.0)

    def test_size_mismatch_raises(self):
        a = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
        b = Image.new("RGBA", (16, 8), (0, 0, 0, 255))
        with self.assertRaises(ValueError):
            compare.image_similarity_pct(a, b)

    def test_known_drift_matches_engine_formula(self):
        # Every pixel differs by 1 unit on a single channel: mean_abs_diff = 1.0,
        # accuracy = 1 - 1/10 = 0.9 -> 90%.
        a = Image.new("RGBA", (8, 8), (100, 100, 100, 255))
        b = Image.new("RGBA", (8, 8), (101, 100, 100, 255))
        self.assertAlmostEqual(compare.image_similarity_pct(a, b), 90.0, places=6)

    def test_half_unit_drift_scores_95(self):
        # Half the pixels differ by 1 unit -> mean_abs_diff = 0.5 -> 95%,
        # the origin's documented "0.5 units scores 95" behavior.
        a = Image.new("RGBA", (2, 1), (100, 100, 100, 255))
        b = a.copy()
        b.putpixel((0, 0), (101, 100, 100, 255))
        self.assertAlmostEqual(compare.image_similarity_pct(a, b), 95.0, places=6)


if __name__ == "__main__":
    unittest.main()
