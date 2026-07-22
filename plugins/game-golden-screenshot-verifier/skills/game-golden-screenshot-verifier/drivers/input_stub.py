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

"""STUB deterministic-state driver — REPLACE THIS for your game.

The runner calls drive() after the game has launched and warmed up, and before
the screenshot is captured. Its job is to put the game into the exact same
visual state every run, so the capture can be compared against a golden.

In the origin project this was a scripted in-engine timeline (fix the sky,
teleport to a fixed point, place a deterministic block grid, lock the camera
looking down). Your game needs its own answer. Good options, roughly in order of
robustness:

  * launch straight into a fixed scene via a launch flag or a saved game / fixed
    seed (add it to launch_args in the config, and this driver can do nothing),
  * navigate a deterministic menu path with scripted input (as below),
  * capture a static screen (main menu, splash) where no input is needed.

This stub does the minimal placeholder the framework was seeded with: it moves
the mouse around a square, then presses Shift a few times. It exists only so the
eval runs end to end out of the box — it does NOT produce a meaningful scene.
Swap the body of drive() for your game's real deterministic-state routine.
"""

from __future__ import annotations

import time


def drive() -> None:
    import pyautogui

    # pyautogui aborts if the mouse is slammed into a screen corner; that safety
    # is unhelpful for scripted input, so turn it off for this driven run.
    pyautogui.FAILSAFE = False

    width, height = pyautogui.size()
    cx, cy = width // 2, height // 2
    half = min(width, height) // 4

    # Move the mouse around a square.
    square = [(cx - half, cy - half), (cx + half, cy - half),
              (cx + half, cy + half), (cx - half, cy + half),
              (cx - half, cy - half)]
    for x, y in square:
        pyautogui.moveTo(x, y, duration=0.25)

    # Press Shift a few times.
    for _ in range(3):
        pyautogui.press("shift")
        time.sleep(0.1)
