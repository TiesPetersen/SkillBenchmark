import math
from dataclasses import dataclass
from typing import List

from scipy import stats as scipy_stats


@dataclass
class Stats:
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    n: int


def _t_critical(df: int, confidence: float) -> float:
    return scipy_stats.t.ppf(1 - (1 - confidence) / 2, df)


def compute_stats(scores: List[float], confidence: float = 0.95) -> Stats:
    n = len(scores)
    mean = sum(scores) / n

    if n < 2:
        return Stats(mean=mean, std=0.0, ci_lower=mean, ci_upper=mean, n=n)

    variance = sum((x - mean) ** 2 for x in scores) / (n - 1)
    std = math.sqrt(variance)
    margin = _t_critical(n - 1, confidence) * std / math.sqrt(n)

    return Stats(
        mean=mean,
        std=std,
        ci_lower=max(0.0, mean - margin),
        ci_upper=mean + margin,
        n=n,
    )


def ci_margin(stats: Stats) -> float:
    return (stats.ci_upper - stats.ci_lower) / 2


def delta_ci_margin(s1: Stats, s2: Stats, confidence: float) -> float:
    """CI margin for the difference s1.mean - s2.mean using Welch's t-interval."""
    if s1.n < 2 or s2.n < 2:
        return float("inf")
    se1 = s1.std / math.sqrt(s1.n)
    se2 = s2.std / math.sqrt(s2.n)
    se_diff = math.sqrt(se1 ** 2 + se2 ** 2)
    # Welch-Satterthwaite degrees of freedom
    df = (se1 ** 2 + se2 ** 2) ** 2 / (se1 ** 4 / (s1.n - 1) + se2 ** 4 / (s2.n - 1))
    return _t_critical(df, confidence) * se_diff
