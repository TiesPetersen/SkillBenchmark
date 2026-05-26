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


def verdict(with_stats: Stats, without_stats: Stats, min_meaningful_delta: float = 5.0) -> str:
    if with_stats.ci_lower > without_stats.ci_upper:
        return "skill_better"
    elif without_stats.ci_lower > with_stats.ci_upper:
        return "baseline_better"
    elif abs(with_stats.mean - without_stats.mean) < min_meaningful_delta:
        # CIs overlap and means are close — no meaningful difference detected
        return "no_difference"
    else:
        # CIs overlap but means diverge — likely a real effect, more runs needed
        return "inconclusive"
