from __future__ import annotations
import random
from typing import Any, List, Optional
from .models import Stage, ReactorMetrics


class ReactorGameEngine:

    def __init__(self, stages: List[Stage], *, energy_per_click: int = 1, peak_window_s: float = 1.0):
        if not stages:
            raise ValueError("Stages is empty")
        for i in range(1, len(stages)):
            if stages[i].energy_required < stages[i - 1].energy_required:
                raise ValueError("energy_required must be upset, not down set")

        self._stages = stages
        self._energy_per_click = int(energy_per_click)
        self._peak_window_s = float(peak_window_s)

        self.metrics = ReactorMetrics()
        self._current_energy: int = 0
        self._stage_idx: int = self._infer_initial_stage_index()

    @property
    def current_energy(self) -> int:
        return self._current_energy

    @property
    def current_stage(self) -> Stage:
        return self._stages[self._stage_idx]

    @property
    def current_stage_index(self) -> int:
        return self._stage_idx

    @property
    def pi_stage_reached(self) -> str:
        return self.current_stage.pi_fragment

    @property
    def current_level(self) -> int:
        return self._infer_level_from_pi_stage(self.pi_stage_reached)

    @property
    def progress_percentage(self) -> float:
        cur_req = self.current_stage.energy_required
        if self._stage_idx == len(self._stages) - 1:
            return 100.0
        next_req = self._stages[self._stage_idx + 1].energy_required
        span = max(1, next_req - cur_req)
        done = max(0, self._current_energy - cur_req)
        return max(0.0, min(100.0, (done / span) * 100.0))

    def register_click(self, *, energy_generated: Optional[int] = None, timestamp_s: Optional[float] = None) -> None:
        e = int(self._energy_per_click if energy_generated is None else energy_generated)
        self._current_energy += e
        self.metrics.energy_total += e
        self.metrics.clicks += 1
        self.metrics.last_click_ts = timestamp_s
        self.metrics.bump_tps(window_s=self._peak_window_s)
        self._advance_stages_if_needed()

    # ------------------------------ build payload ------------------------------

    def build_end_payload(
        self,
        *,
        tps_mode: str = "avg",                    # 'avg' | 'peak'
        override_level: Optional[int] = None,
        override_pi_stage: Optional[str] = None,
    ) -> dict[str, Any]:

        dur = self.metrics.duration_s()
        tps_val = self.metrics.peak_tps if tps_mode == "peak" else self.metrics.avg_tps()

        pi_stage_out = str(override_pi_stage) if override_pi_stage is not None else self.pi_stage_reached
        level_out = int(override_level) if override_level is not None else self._infer_level_from_pi_stage(pi_stage_out)

        return {
            "score": int(self.metrics.energy_total),
            "tps": int(round(tps_val)) if tps_mode in ("avg", "peak") else int(random.randint(8, 20)),
            "duration": int(round(dur)),
            "level": level_out,
            "piStageReached": pi_stage_out,
        }

    # ------------------------------ internal logic  ------------------------------

    def _infer_initial_stage_index(self) -> int:
        idx = 0
        for i, st in enumerate(self._stages):
            if st.energy_required <= 0:
                idx = i
            else:
                break
        return idx

    def _advance_stages_if_needed(self) -> None:
        while self._stage_idx + 1 < len(self._stages):
            next_req = self._stages[self._stage_idx + 1].energy_required
            if self._current_energy >= next_req:
                self._stage_idx += 1
            else:
                break

    @staticmethod
    def _infer_level_from_pi_stage(pi_stage: str) -> int:
        try:
            head = pi_stage.split('.', 1)[0].strip()
            return int(head)
        except Exception:
            return 9
