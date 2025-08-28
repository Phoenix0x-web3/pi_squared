from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Stage:
    """
    Ступень раскрытия π².
    energy_required — накопленная энергия, НУЖНАЯ, чтобы ДОСТИЧЬ ЭТОЙ ступени.
    """
    pi_fragment: str
    energy_required: int


@dataclass
class ReactorMetrics:
    """Агрегируемые метрики сессии."""
    clicks: int = 0
    energy_total: int = 0
    t0: float = field(default_factory=time.time)
    last_click_ts: Optional[float] = None
    _tap_times: list[float] = field(default_factory=list)
    peak_tps: float = 0.0

    def duration_s(self) -> float:
        return max(0.0, time.time() - self.t0)

    def avg_tps(self) -> float:
        dur = self.duration_s()
        return (self.clicks / dur) if dur > 0 else 0.0

    def bump_tps(self, window_s: float = 1.0) -> None:
        now = time.time()
        self._tap_times.append(now)
        cutoff = now - window_s
        while self._tap_times and self._tap_times[0] < cutoff:
            self._tap_times.pop(0)
        current_tps = len(self._tap_times) / window_s
        if current_tps > self.peak_tps:
            self.peak_tps = current_tps
