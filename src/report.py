import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, List, Tuple

from .evaluator import EvaluationResult
from .stats import Stats, compute_stats, verdict
from .task import Task


@dataclass
class RunPair:
    run_index: int
    with_skill: EvaluationResult
    without_skill: EvaluationResult
    with_skill_output: str
    without_skill_output: str
    with_skill_tokens: int
    without_skill_tokens: int


def _serializable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serializable(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    return obj


_VERDICT_LABELS = {
    "skill_better": "Skill improves output",
    "baseline_better": "Baseline outperforms skill",
    "inconclusive": "Inconclusive — confidence intervals overlap",
}


def write_results(
    task: Task,
    runs: List[RunPair],
    confidence: float,
    results_dir: str,
    skill_name: str,
) -> Tuple[str, str]:
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = task.name.lower().replace(" ", "_")
    base = os.path.join(results_dir, f"{skill_name}__{slug}__{timestamp}")

    with_scores = [r.with_skill.total_score for r in runs]
    without_scores = [r.without_skill.total_score for r in runs]
    ws = compute_stats(with_scores, confidence)
    ns = compute_stats(without_scores, confidence)
    v = verdict(ws, ns)

    # --- JSON ---
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "skill": skill_name,
            "task": task.name,
            "timestamp": timestamp,
            "verdict": v,
            "with_skill_stats": _serializable(ws),
            "without_skill_stats": _serializable(ns),
            "runs": [_serializable(r) for r in runs],
        }, f, indent=2)

    # --- Markdown ---
    ci_pct = int(confidence * 100)
    md_lines = [
        f"# Benchmark — {task.name}",
        f"*Skill: `{skill_name}` | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        f"**Verdict: {_VERDICT_LABELS[v]}**",
        "",
        "## Score summary",
        "",
        "| | With skill | Without skill |",
        "|---|---|---|",
        f"| Mean score | {ws.mean:.1f} / {task.rubric.total} | {ns.mean:.1f} / {task.rubric.total} |",
        f"| Std dev | {ws.std:.1f} | {ns.std:.1f} |",
        f"| {ci_pct}% CI | [{ws.ci_lower:.1f}, {ws.ci_upper:.1f}] | [{ns.ci_lower:.1f}, {ns.ci_upper:.1f}] |",
        f"| Runs | {ws.n} | {ns.n} |",
        "",
        "## Per-run scores",
        "",
        "| Run | With skill | Without skill |",
        "|---|---|---|",
    ]
    for r in runs:
        md_lines.append(f"| {r.run_index + 1} | {r.with_skill.total_score} | {r.without_skill.total_score} |")

    md_lines += [
        "",
        "## Criterion breakdown (mean across runs)",
        "",
        "| Criterion | With skill | Without skill | Max |",
        "|---|---|---|---|",
    ]
    for i, crit in enumerate(runs[0].with_skill.criteria_scores):
        w_avg = sum(r.with_skill.criteria_scores[i].score for r in runs) / len(runs)
        n_avg = sum(r.without_skill.criteria_scores[i].score for r in runs) / len(runs)
        md_lines.append(f"| {crit.name} | {w_avg:.1f} | {n_avg:.1f} | {crit.max_score} |")

    md_lines += [
        "",
        "## Token usage",
        "",
        "| Run | With skill | Without skill |",
        "|---|---|---|",
    ]
    for r in runs:
        md_lines.append(f"| {r.run_index + 1} | {r.with_skill_tokens} | {r.without_skill_tokens} |")
    md_lines.append("")

    md_path = base + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return json_path, md_path
