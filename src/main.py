import os
import re
import sys
from datetime import datetime
from typing import Optional

import anthropic
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

_FRONTMATTER_NAME_RE = re.compile(r"^---\s*\nname:\s*(.+?)\s*\n", re.DOTALL)

from .config import load_config
from .evaluator import evaluate_output
from .report import RunPair, TaskSummary, create_run_dir, write_task_results, write_overview
from .runner import run_task
from .stats import ci_margin, compute_stats, delta_ci_margin
from .task import load_all_tasks

console = Console()


def _skill_name(content: Optional[str], skill_path: str) -> str:
    if content:
        match = _FRONTMATTER_NAME_RE.match(content)
        if match:
            return match.group(1)
    return os.path.basename(os.path.dirname(skill_path)) or os.path.splitext(os.path.basename(skill_path))[0]


def _load_skill(skill_path: str) -> Optional[str]:
    if not os.path.exists(skill_path):
        console.print(f"  [yellow]Warning:[/yellow] no skill file found at '{skill_path}' — running without skill comparison only")
        return None
    with open(skill_path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    console.print()
    console.rule("[bold]SkillBenchmark[/bold]")
    console.print()

    with console.status("[dim]Loading config...[/dim]", spinner="dots"):
        config = load_config()
    console.print("  [green]✓[/green] Config loaded")

    with console.status("[dim]Initialising Anthropic client...[/dim]", spinner="dots"):
        client = anthropic.Anthropic(api_key=config.api_key)
    console.print("  [green]✓[/green] Anthropic client ready")

    with console.status("[dim]Loading skill...[/dim]", spinner="dots"):
        skill_content = _load_skill(config.skill_path)
        skill_name = _skill_name(skill_content, config.skill_path)
    if skill_content:
        console.print(f"  [green]✓[/green] Skill loaded: [bold]{skill_name}[/bold]")
    else:
        console.print(f"  [yellow]![/yellow] No skill found — without skill-only mode")

    with console.status("[dim]Loading tasks...[/dim]", spinner="dots"):
        tasks = load_all_tasks(config.tasks_dir)
    if not tasks:
        console.print(f"  [red]✗[/red] No task files found in '{config.tasks_dir}/'")
        sys.exit(1)
    console.print(f"  [green]✓[/green] {len(tasks)} task{'s' if len(tasks) != 1 else ''} loaded")

    n_runs = config.number_of_runs_per_task
    n_judges = config.number_of_judges_per_run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = create_run_dir(config.results_dir, skill_name, timestamp)
    console.print(f"  [green]✓[/green] Output directory: [dim]{run_dir}[/dim]")

    console.print()
    console.print("  [dim]Runner :[/dim] " + f"{config.runner_model}  (temp={config.runner_temperature})")
    console.print("  [dim]Judge  :[/dim] " + f"{config.judge_model}  (temp={config.judge_temperature})")
    console.print("  [dim]Runs   :[/dim] " + f"{n_runs} per task  |  Judges: {n_judges} per run")
    console.print()
    console.rule()
    console.print()

    summaries: list[TaskSummary] = []
    total_tasks = len(tasks)
    total_api_calls = total_tasks * n_runs * (2 + 2 * n_judges)

    for task_idx, task in enumerate(tasks):
        console.print(f"[bold]Task {task_idx + 1}/{total_tasks}:[/bold] {task.name}")
        run_pairs = []

        for i in range(n_runs):
            console.print(f"  [dim]Run {i + 1}/{n_runs}[/dim]")

            with console.status(
                f"    [cyan]Running without skill[/cyan] [dim](no skill, waiting for API...)[/dim]",
                spinner="dots",
            ):
                without = run_task(
                    client, config.runner_model, config.runner_temperature,
                    config.runner_max_tokens, task, skill_content=None,
                )
            console.print(
                f"    [dim]Without skill[/dim]     [green]done[/green]"
                f"  [dim]{without.input_tokens + without.output_tokens} tokens[/dim]"
            )

            with console.status(
                f"    [cyan]Running with skill[/cyan] [dim](waiting for API...)[/dim]",
                spinner="dots",
            ):
                with_skill = run_task(
                    client, config.runner_model, config.runner_temperature,
                    config.runner_max_tokens, task, skill_content=skill_content,
                )
            console.print(
                f"    [dim]With skill[/dim]   [green]done[/green]"
                f"  [dim]{with_skill.input_tokens + with_skill.output_tokens} tokens[/dim]"
            )

            without_evals = []
            for j in range(n_judges):
                judge_str = f"judge {j + 1}/{n_judges}" if n_judges > 1 else "judge"
                with console.status(
                    f"    [cyan]Judging without skill[/cyan] [dim]({judge_str}, waiting for API...)[/dim]",
                    spinner="dots",
                ):
                    ev = evaluate_output(
                        client, config.judge_model, config.judge_temperature,
                        config.judge_max_tokens, task.rubric, without.output,
                    )
                without_evals.append(ev)
                j_label = f"[dim]j{j + 1}[/dim] " if n_judges > 1 else ""
                console.print(
                    f"    [dim]Judge without skill[/dim]   {j_label}[green]done[/green]"
                    f"  score=[bold]{ev.total_score}/{ev.max_score}[/bold]"
                )

            with_evals = []
            for j in range(n_judges):
                judge_str = f"judge {j + 1}/{n_judges}" if n_judges > 1 else "judge"
                with console.status(
                    f"    [cyan]Judging with-skill[/cyan] [dim]({judge_str}, waiting for API...)[/dim]",
                    spinner="dots",
                ):
                    ev = evaluate_output(
                        client, config.judge_model, config.judge_temperature,
                        config.judge_max_tokens, task.rubric, with_skill.output,
                    )
                with_evals.append(ev)
                j_label = f"[dim]j{j + 1}[/dim] " if n_judges > 1 else ""
                console.print(
                    f"    [dim]Judge with-skill[/dim]  {j_label}[green]done[/green]"
                    f"  score=[bold]{ev.total_score}/{ev.max_score}[/bold]"
                )

            run_pairs.append(RunPair(
                run_index=i,
                with_skill=with_evals,
                without_skill=without_evals,
                with_skill_output=with_skill.output,
                without_skill_output=without.output,
                with_skill_tokens=with_skill.input_tokens + with_skill.output_tokens,
                without_skill_tokens=without.input_tokens + without.output_tokens,
            ))

        ws = compute_stats([e.total_score for r in run_pairs for e in r.with_skill], config.confidence_level)
        ns = compute_stats([e.total_score for r in run_pairs for e in r.without_skill], config.confidence_level)

        json_path, md_path, summary = write_task_results(
            task, run_pairs, config.confidence_level, run_dir, skill_name, timestamp,
        )
        summaries.append(summary)

        ci_pct = int(config.confidence_level * 100)
        delta = ws.mean - ns.mean
        d_margin = delta_ci_margin(ws, ns, config.confidence_level)
        delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"
        console.print(
            f"\n  [dim]with-skill:[/dim] [bold]{ws.mean:.1f} ± {ci_margin(ws):.1f}[/bold]"
            f"  [dim]without skill:[/dim] [bold]{ns.mean:.1f} ± {ci_margin(ns):.1f}[/bold]"
            f"  [dim]delta: {delta_str} ± {d_margin:.1f}  ({ci_pct}% CI)[/dim]"
        )
        console.print()

    config_snapshot = {
        "runner_model": config.runner_model,
        "judge_model": config.judge_model,
        "number_of_runs_per_task": config.number_of_runs_per_task,
        "number_of_judges_per_run": config.number_of_judges_per_run,
        "runner_temperature": config.runner_temperature,
        "confidence_level": config.confidence_level,
    }
    overview_path = write_overview(summaries, run_dir, skill_name, timestamp, config_snapshot)

    console.rule()
    console.print()

    # Final summary table
    ci_pct = int(config.confidence_level * 100)
    console.print(f"[bold]Summary[/bold]  [dim]({ci_pct}% CI)[/dim]")
    console.print()
    for s in summaries:
        ws, ns = s.with_skill_stats, s.without_skill_stats
        delta = ws.mean - ns.mean
        d_margin = delta_ci_margin(ws, ns, config.confidence_level)
        delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"
        console.print(
            f"  [dim]{s.task_name}[/dim]\n"
            f"    with-skill [bold]{ws.mean:.1f} ± {ci_margin(ws):.1f}[/bold]"
            f"  without skill [bold]{ns.mean:.1f} ± {ci_margin(ns):.1f}[/bold]"
            f"  [dim]delta {delta_str} ± {d_margin:.1f}[/dim]"
        )

    console.print()
    console.print(f"[bold]Done.[/bold]  Results: [dim]{run_dir}[/dim]")
    console.print(f"         Overview: [dim]{overview_path}[/dim]")
    console.print()
