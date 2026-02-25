from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ControlScoreInput:
    category: str
    compliance_value: float
    criticality_weight: float
    max_score: float = 100.0


@dataclass(frozen=True)
class ScoreSummary:
    score_global: float
    risk_global: float
    semaphore: str
    per_category: dict[str, float]


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calculate_score_summary(
    controls: Iterable[ControlScoreInput],
    green_threshold: float = 85.0,
    yellow_threshold: float = 70.0,
    critical_weight_threshold: float = 2.0,
    critical_compliance_threshold: float = 0.5,
) -> ScoreSummary:
    per_category_num: dict[str, float] = {}
    per_category_den: dict[str, float] = {}
    total_num = 0.0
    total_den = 0.0
    force_red = False

    for control in controls:
        c = _bounded(control.compliance_value, 0.0, 1.0)
        w = max(control.criticality_weight, 0.000001)
        m = max(control.max_score, 0.000001)

        s_i = c * m
        p_i = s_i * w

        per_category_num[control.category] = per_category_num.get(control.category, 0.0) + p_i
        per_category_den[control.category] = per_category_den.get(control.category, 0.0) + (m * w)

        total_num += p_i
        total_den += m * w

        if w >= critical_weight_threshold and c < critical_compliance_threshold:
            force_red = True

    per_category: dict[str, float] = {}
    for category, den in per_category_den.items():
        per_category[category] = round((per_category_num[category] / den) * 100, 2) if den else 0.0

    score_global = round((total_num / total_den) * 100, 2) if total_den else 0.0
    risk_global = round(100.0 - score_global, 2)

    if force_red or score_global < yellow_threshold:
        semaphore = "red"
    elif score_global < green_threshold:
        semaphore = "yellow"
    else:
        semaphore = "green"

    return ScoreSummary(
        score_global=score_global,
        risk_global=risk_global,
        semaphore=semaphore,
        per_category=per_category,
    )
