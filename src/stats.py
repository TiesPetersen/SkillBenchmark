import math
from dataclasses import dataclass
from typing import List

# t critical values keyed by (degrees_of_freedom, confidence_level)
_T_TABLE = {
    (1, 0.90): 6.314,  (1, 0.95): 12.706, (1, 0.99): 63.657,
    (2, 0.90): 2.920,  (2, 0.95): 4.303,  (2, 0.99): 9.925,
    (3, 0.90): 2.353,  (3, 0.95): 3.182,  (3, 0.99): 5.841,
    (4, 0.90): 2.132,  (4, 0.95): 2.776,  (4, 0.99): 4.604,
    (5, 0.90): 2.015,  (5, 0.95): 2.571,  (5, 0.99): 4.032,
    (9, 0.90): 1.833,  (9, 0.95): 2.262,  (9, 0.99): 3.250,
    (14, 0.90): 1.761, (14, 0.95): 2.145, (14, 0.99): 2.977,
    (19, 0.90): 1.729, (19, 0.95): 2.093, (19, 0.99): 2.861,
    (29, 0.90): 1.699, (29, 0.95): 2.045, (29, 0.99): 2.756,
}


@dataclass
class Stats:
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    n: int


def _t_critical(df: int, confidence: float) -> float:
    key = (df, confidence)
    if key in _T_TABLE:
        return _T_TABLE[key]
    try:
        from scipy import stats as scipy_stats
        return scipy_stats.t.ppf(1 - (1 - confidence) / 2, df)
    except ImportError:
        # Normal approximation fallback for large n
        if confidence >= 0.99:
            return 2.576
        elif confidence >= 0.95:
            return 1.960
        return 1.645


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


def verdict(with_stats: Stats, without_stats: Stats) -> str:
    if with_stats.ci_lower > without_stats.ci_upper:
        return "skill_better"
    elif without_stats.ci_lower > with_stats.ci_upper:
        return "baseline_better"
    return "inconclusive"
