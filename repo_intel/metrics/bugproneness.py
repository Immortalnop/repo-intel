"""Bug-proneness / risk scoring per file."""

from __future__ import annotations

from datetime import datetime

from ..config import DEFAULT, Config
from . import churn as churn_m
from . import ownership as own_m


def file_risk_score(
    churn: int,
    commits: int,
    bugfixes: int,
    last: datetime | None,
    author_commits: dict[str, int],
    max_churn: int,
    now: datetime,
    cfg: Config = DEFAULT,
) -> tuple[float, dict[str, float]]:
    """Composite 0..100 risk score + its signal breakdown.

    Weighted blend of four explainable signals (weights from config):
      churn        instability
      bugfix_ratio defect density
      recency      recently churned code is riskier for the next release
      ownership    single-owner files are fragile
    """
    signals = {
        "churn": churn_m.normalize(churn, max_churn),
        "bugfix_ratio": bugfixes / commits if commits else 0.0,
        "recency": churn_m.recency_weight(last, now, cfg.recency_half_life_days),
        "ownership": own_m.ownership_share(author_commits)[1],
    }
    w = cfg.risk_weights
    score = sum(w[k] * signals[k] for k in w) * 100.0
    return round(score, 1), {k: round(v, 3) for k, v in signals.items()}
