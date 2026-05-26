import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from .task import Task

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def strip_frontmatter(content: str) -> str:
    return _FRONTMATTER_RE.sub("", content, count=1).lstrip()


@dataclass
class RunResult:
    output: str
    input_tokens: int
    output_tokens: int
    used_skill: bool


def run_task(
    client: anthropic.Anthropic,
    model: str,
    temperature: float,
    max_tokens: int,
    task: Task,
    skill_content: Optional[str] = None,
) -> RunResult:
    user_message = ""
    if task.prompt.context:
        user_message += task.prompt.context.strip() + "\n\n"
    user_message += task.prompt.description.strip()

    system = strip_frontmatter(skill_content) if skill_content else "You are a helpful assistant."

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return RunResult(
        output=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        used_skill=skill_content is not None,
    )
