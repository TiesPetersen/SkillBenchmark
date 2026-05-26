import os
import yaml
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    number_of_runs_per_task: int
    number_of_judges_per_run: int
    runner_model: str
    judge_model: str
    runner_temperature: float
    runner_max_tokens: int
    judge_temperature: float
    judge_max_tokens: int
    skill_path: str
    tasks_dir: str
    results_dir: str
    confidence_level: float
    min_meaningful_delta: float
    api_key: str


def load_config(config_path: str = "config.yml") -> Config:
    load_dotenv()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set — add it to your .env file")

    return Config(
        number_of_runs_per_task=data.get("number_of_runs_per_task", 3),
        number_of_judges_per_run=data.get("number_of_judges_per_run", 1),
        runner_model=data.get("runner_model", "claude-sonnet-4-6"),
        judge_model=data.get("judge_model", "claude-sonnet-4-6"),
        runner_temperature=data.get("runner_temperature", 0.7),
        runner_max_tokens=data.get("runner_max_tokens", 4096),
        judge_temperature=data.get("judge_temperature", 0.0),
        judge_max_tokens=data.get("judge_max_tokens", 1024),
        skill_path=data.get("skill_path", "skill.md"),
        tasks_dir=data.get("tasks_dir", "tasks"),
        results_dir=data.get("results_dir", "results"),
        confidence_level=data.get("confidence_level", 0.95),
        min_meaningful_delta=data.get("min_meaningful_delta", 5.0),
        api_key=api_key,
    )
