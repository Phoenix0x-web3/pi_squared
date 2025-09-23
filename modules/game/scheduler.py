# modules/game/scheduler.py
import random
import time
from typing import List, Optional, Tuple


class TargetScheduler:
    def __init__(self, colors: List[str], interval_ms: int, *, start_color: Optional[str] = None):
        self.colors = colors[:]
        self.interval_ms = int(interval_ms)
        self._cur = start_color if (start_color in self.colors) else random.choice(self.colors)
        self._last = time.perf_counter()
        self._last_change = self._last

    @property
    def last_change_ms(self) -> int:
        return int((self._last - self._last_change) * 1000.0)

    def set_speed(self, interval_ms: int):
        self.interval_ms = int(interval_ms)
        now = time.perf_counter()

        self._last = now

    def tick(self) -> Tuple[str, int, bool]:
        now = time.perf_counter()
        elapsed_ms = (now - self._last) * 1000.0
        changed = False
        if elapsed_ms >= self.interval_ms:
            prev_color = self._cur
            nxt = prev_color
            while nxt == prev_color:
                nxt = random.choice(self.colors)
            self._cur = nxt
            self._last_change = now
            self._last = now
            changed = True
            elapsed_ms = 0.0
        ms_left = max(0, self.interval_ms - int(elapsed_ms))
        return self._cur, ms_left, changed
