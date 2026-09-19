"""Predictive risk analysis: trend / regression over the commit timeline.

Uses a plain least-squares linear fit (no external ML dependency) on the
monthly activity series to project where defect pressure is heading.
"""

from __future__ import annotations


def _linreg(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) via ordinary least squares."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return slope, my - slope * mx


def predict_risk(activity: list[dict]) -> dict:
    """Project bug-fix-rate and churn trend from monthly activity.

    activity: [{month, commits, bugfixes, churn}, ...] in chronological order.
    """
    months = [a for a in activity if a["commits"] > 0]
    if len(months) < 3:
        return {
            "trend": "INSUFFICIENT_DATA",
            "months_analyzed": len(months),
            "note": "Need >=3 active months for a trend.",
        }

    xs = [float(i) for i in range(len(months))]
    bug_rate = [a["bugfixes"] / a["commits"] for a in months]
    churn = [float(a["churn"]) for a in months]

    b_slope, b_int = _linreg(xs, bug_rate)
    c_slope, _ = _linreg(xs, churn)

    nxt = max(0.0, b_slope * len(months) + b_int)
    # classify: slope per month in bug-fix-rate points
    if b_slope > 0.03:
        trend, risk = "DETERIORATING", "high"
    elif b_slope < -0.03:
        trend, risk = "IMPROVING", "low"
    else:
        trend, risk = "STABLE", "medium"

    return {
        "trend": trend,
        "risk_level": risk,
        "months_analyzed": len(months),
        "bugfix_rate_slope": round(b_slope, 4),
        "churn_slope": round(c_slope, 2),
        "projected_next_month_bugfix_rate": round(nxt, 3),
        "note": (
            f"Bug-fix rate is {'rising' if b_slope>0 else 'falling'} "
            f"~{abs(b_slope)*100:.1f} pts/month; churn "
            f"{'rising' if c_slope>0 else 'falling'}."
        ),
    }
