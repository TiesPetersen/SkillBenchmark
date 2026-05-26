import os
import yaml
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RubricLevel:
    range: Tuple[int, int]
    description: str


@dataclass
class RubricCriterion:
    name: str
    points: int
    levels: List[RubricLevel]


@dataclass
class Rubric:
    context: str
    criteria: List[RubricCriterion]

    @property
    def total(self) -> int:
        return sum(c.points for c in self.criteria)


@dataclass
class TaskPrompt:
    context: str
    description: str


@dataclass
class Task:
    name: str
    version: str
    prompt: TaskPrompt
    rubric: Rubric
    file_path: str


def load_task(file_path: str) -> Task:
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    task_data = data["task"]
    rubric_data = data["rubric"]

    criteria = []
    for c in rubric_data["criteria"]:
        levels = [
            RubricLevel(range=tuple(lvl["range"]), description=lvl["description"])
            for lvl in c["levels"]
        ]
        criteria.append(RubricCriterion(name=c["name"], points=c["points"], levels=levels))

    return Task(
        name=data["name"],
        version=str(data.get("version", "1.0")),
        prompt=TaskPrompt(
            context=task_data.get("context", ""),
            description=task_data["description"],
        ),
        rubric=Rubric(
            context=rubric_data.get("context", ""),
            criteria=criteria,
        ),
        file_path=file_path,
    )


def load_all_tasks(tasks_dir: str) -> List[Task]:
    tasks = []
    for filename in sorted(os.listdir(tasks_dir)):
        if filename.endswith((".yml", ".yaml")):
            tasks.append(load_task(os.path.join(tasks_dir, filename)))
    return tasks
