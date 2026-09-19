"""Churn & recency metrics."""

from __future__ import annotations

import math
from datetime import datetime

from ..config import DEFAULT


def normalize(value: float, max_value: float) -> float:
    """Log-scaled 0..1 normalization to tame heavy-tailed churn."""
    if max_value <= 0:
        return 0.0
    return math.log1p(value) / math.log1p(max_value)


def recency_weight(
    last: datetime | None, now: datetime, half_life_days: float | None = None
) -> float:
    """1.0 for code touched today, halving every `half_life_days`."""
    if last is None:
        return 0.0
    hl = half_life_days or DEFAULT.recency_half_life_days
    age_days = max((now - last).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / hl)


def max_churn(history) -> int:
    return max((f.churn for f in history.files.values()), default=1)
