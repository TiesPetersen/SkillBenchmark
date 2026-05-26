import os
import re
import sys
from typing import Optional

import anthropic

_FRONTMATTER_NAME_RE = re.compile(r"^---\s*\nname:\s*(.+?)\s*\n", re.DOTALL)

from .config import load_config
from .evaluator import evaluate_output
from .report import RunPair, write_results
from .runner import run_task
from .stats import compute_stats, verdict
from .task import load_all_tasks


def _skill_name(content: Optional[str], skill_path: str) -> str:
    if content:
        match = _FRONTMATTER_NAME_RE.match(content)
        if match:
            return match.group(1)
    return os.path.basename(os.path.dirname(skill_path)) or os.path.splitext(os.path.basename(skill_path))[0]


def _load_skill(skill_path: str) -> Optional[str]:
    if not os.path.exists(skill_path):
        print(f"Warning: no skill file found at '{skill_path}' — running baseline comparison only")
        return None
    with open(skill_path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    config = load_config()
    client = anthropic.Anthropic(api_key=config.api_key)

    skill_content = _load_skill(config.skill_path)
    skill_name = _skill_name(skill_content, config.skill_path)

    tasks = load_all_tasks(config.tasks_dir)
    if not tasks:
        print(f"No task files found in '{config.tasks_dir}/'")
        sys.exit(1)

    n_runs = config.number_of_runs_per_task
    n_judges = config.number_of_judges_per_run

    print(f"Tasks:  {len(tasks)}")
    print(f"Runs:   {n_runs} per task")
    print(f"Judges: {n_judges} per run")
    print(f"Runner: {config.runner_model}  (temperature={config.runner_temperature})")
    print(f"Judge:  {config.judge_model}  (temperature={config.judge_temperature})")
    print(f"Skill:  {skill_name}")
    print()

    _VERDICT_LABELS = {
        "skill_better":    "SKILL BETTER",
        "baseline_better": "BASELINE BETTER",
        "inconclusive":    "INCONCLUSIVE",
    }

    for task in tasks:
        print(f"[Task] {task.name}")
        run_pairs = []

        for i in range(n_runs):
            print(f"  Run {i + 1}/{n_runs} ...", end=" ", flush=True)

            without = run_task(client, config.runner_model, config.runner_temperature, task, skill_content=None)
            with_skill = run_task(client, config.runner_model, config.runner_temperature, task, skill_content=skill_content)

            without_eval = evaluate_output(client, config.judge_model, config.judge_temperature, task.rubric, without.output, n_judges)
            with_eval = evaluate_output(client, config.judge_model, config.judge_temperature, task.rubric, with_skill.output, n_judges)

            run_pairs.append(RunPair(
                run_index=i,
                with_skill=with_eval,
                without_skill=without_eval,
                with_skill_output=with_skill.output,
                without_skill_output=without.output,
                with_skill_tokens=with_skill.input_tokens + with_skill.output_tokens,
                without_skill_tokens=without.input_tokens + without.output_tokens,
            ))

            print(f"with={with_eval.total_score}  without={without_eval.total_score}")

        ws = compute_stats([r.with_skill.total_score for r in run_pairs], config.confidence_level)
        ns = compute_stats([r.without_skill.total_score for r in run_pairs], config.confidence_level)
        v = verdict(ws, ns)

        json_path, md_path = write_results(task, run_pairs, config.confidence_level, config.results_dir, skill_name)

        print(f"  => {_VERDICT_LABELS[v]}  (with: {ws.mean:.1f} | without: {ns.mean:.1f})")
        print(f"     {json_path}")
        print(f"     {md_path}")
        print()
