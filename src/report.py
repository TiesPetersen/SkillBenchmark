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
    with_skill: List[EvaluationResult]
    without_skill: List[EvaluationResult]
    with_skill_output: str
    without_skill_output: str
    with_skill_tokens: int
    without_skill_tokens: int


@dataclass
class TaskSummary:
    task_name: str
    verdict: str
    with_skill_stats: Stats
    without_skill_stats: Stats
    md_filename: str


def _serializable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serializable(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    return obj


_VERDICT_LABELS = {
    "skill_better":    "Skill improves output",
    "baseline_better": "Baseline outperforms skill",
    "inconclusive":    "Inconclusive — confidence intervals overlap",
}

_VERDICT_SYMBOLS = {
    "skill_better":    "SKILL BETTER",
    "baseline_better": "BASELINE BETTER",
    "inconclusive":    "INCONCLUSIVE",
}


def create_run_dir(results_dir: str, skill_name: str, timestamp: str) -> str:
    run_dir = os.path.join(results_dir, f"{skill_name}__{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_task_results(
    task: Task,
    runs: List[RunPair],
    confidence: float,
    run_dir: str,
    skill_name: str,
    timestamp: str,
) -> Tuple[str, str, TaskSummary]:
    slug = task.name.lower().replace(" ", "_")

    with_scores = [e.total_score for r in runs for e in r.with_skill]
    without_scores = [e.total_score for r in runs for e in r.without_skill]
    ws = compute_stats(with_scores, confidence)
    ns = compute_stats(without_scores, confidence)
    v = verdict(ws, ns)

    # --- JSON ---
    json_path = os.path.join(run_dir, f"{slug}.json")
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
        f"# {task.name}",
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
        f"| Samples (runs × judges) | {ws.n} | {ns.n} |",
        "",
        "## Per-run scores",
        "",
        "| Run | Judge | With skill | Without skill |",
        "|---|---|---|---|",
    ]
    for r in runs:
        for j, (w_e, n_e) in enumerate(zip(r.with_skill, r.without_skill)):
            run_label = str(r.run_index + 1) if j == 0 else ""
            md_lines.append(f"| {run_label} | {j + 1} | {w_e.total_score} | {n_e.total_score} |")

    md_lines += [
        "",
        "## Criterion breakdown (mean across runs)",
        "",
        "| Criterion | With skill | Without skill | Max |",
        "|---|---|---|---|",
    ]
    all_with = [e for r in runs for e in r.with_skill]
    all_without = [e for r in runs for e in r.without_skill]
    for i, crit in enumerate(all_with[0].criteria_scores):
        w_avg = sum(e.criteria_scores[i].score for e in all_with) / len(all_with)
        n_avg = sum(e.criteria_scores[i].score for e in all_without) / len(all_without)
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

    md_filename = f"{slug}.md"
    md_path = os.path.join(run_dir, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return json_path, md_path, TaskSummary(
        task_name=task.name,
        verdict=v,
        with_skill_stats=ws,
        without_skill_stats=ns,
        md_filename=md_filename,
    )


def write_overview(
    summaries: List[TaskSummary],
    run_dir: str,
    skill_name: str,
    timestamp: str,
    config_snapshot: dict,
) -> str:
    ci_pct = int(config_snapshot.get("confidence_level", 0.95) * 100)
    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

    skill_better = sum(1 for s in summaries if s.verdict == "skill_better")
    baseline_better = sum(1 for s in summaries if s.verdict == "baseline_better")
    inconclusive = sum(1 for s in summaries if s.verdict == "inconclusive")

    lines = [
        f"# SkillBenchmark — {skill_name}",
        f"*{dt}*",
        "",
        "## Run configuration",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Skill | `{skill_name}` |",
        f"| Runner model | `{config_snapshot.get('runner_model', '—')}` |",
        f"| Judge model | `{config_snapshot.get('judge_model', '—')}` |",
        f"| Runs per task | {config_snapshot.get('number_of_runs_per_task', '—')} |",
        f"| Judges per run | {config_snapshot.get('number_of_judges_per_run', '—')} |",
        f"| Runner temperature | {config_snapshot.get('runner_temperature', '—')} |",
        f"| Confidence level | {ci_pct}% |",
        "",
        "## Summary",
        "",
        f"**{len(summaries)} task(s)** — "
        f"{skill_better} skill better · {baseline_better} baseline better · {inconclusive} inconclusive",
        "",
        "| Task | Verdict | With skill | Without skill | Delta |",
        "|---|---|---|---|---|",
    ]

    for s in summaries:
        ws, ns = s.with_skill_stats, s.without_skill_stats
        delta = ws.mean - ns.mean
        delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"
        lines.append(
            f"| [{s.task_name}]({s.md_filename}) "
            f"| {_VERDICT_SYMBOLS[s.verdict]} "
            f"| {ws.mean:.1f} [{ws.ci_lower:.1f}, {ws.ci_upper:.1f}] "
            f"| {ns.mean:.1f} [{ns.ci_lower:.1f}, {ns.ci_upper:.1f}] "
            f"| {delta_str} |"
        )

    lines.append("")

    overview_path = os.path.join(run_dir, "overview.md")
    with open(overview_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return overview_path
