"""
Timekeeper: paces the simulation loop to the configured target frame
rate and reports a clamped delta-time each step.
"""
from __future__ import annotations
import time


class Timekeeper:
    def __init__(self, cfg):
        self.cfg = cfg
        self._frame_time = 1.0 / cfg.TARGET_FPS
        self._last = time.perf_counter()

    def step(self) -> float:
        now = time.perf_counter()
        elapsed = now - self._last

        remaining = self._frame_time - elapsed
        if remaining > 0:
            time.sleep(remaining)
            now = time.perf_counter()
            elapsed = now - self._last

        self._last = now
        return min(elapsed, self.cfg.MAX_DT)
