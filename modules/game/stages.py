from __future__ import annotations

from typing import List

from .models import Stage

PI_FRAGMENTS = [
    "9",
    "9.8",
    "9.86",
    "9.869",
    "9.8696",
    "9.86960",
    "9.869604",
    "9.8696044",
]

ENERGY_THRESHOLDS = [
    0,  # '9'
    15,  # '9.8'
    30,  # '9.86'
    45,  # '9.869'
    60,  # '9.8696'
    80,  # '9.86960'
    105,  # '9.869604'
    170,  # '9.8696044' (final)
]


def default_stage_plan() -> List[Stage]:
    if len(PI_FRAGMENTS) != len(ENERGY_THRESHOLDS):
        raise ValueError("PI_FRAGMENTS и ENERGY_THRESHOLDS must be the same")
    stages = [Stage(pi_fragment=f, energy_required=int(t)) for f, t in zip(PI_FRAGMENTS, ENERGY_THRESHOLDS)]
    for i in range(1, len(stages)):
        if stages[i].energy_required < stages[i - 1].energy_required:
            raise ValueError("energy_required must determinate for each stage")
    return stages
