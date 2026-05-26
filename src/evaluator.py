import json
from dataclasses import dataclass
from typing import List

import anthropic

from .task import Rubric


@dataclass
class CriterionScore:
    name: str
    score: int
    max_score: int
    reasoning: str


@dataclass
class EvaluationResult:
    criteria_scores: List[CriterionScore]
    total_score: int
    max_score: int


def _build_system_prompt(rubric: Rubric) -> str:
    lines = [
        "You are an objective evaluator. Score the provided output strictly using the rubric below.",
        "Do not reward or penalise based on topic, style, or your own preferences — only the rubric criteria matter.",
        "",
    ]

    if rubric.context:
        lines += ["CONTEXT:", rubric.context.strip(), ""]

    criterion_names = [c.name for c in rubric.criteria]
    lines += [
        f"RUBRIC ({len(rubric.criteria)} criteria, {rubric.total} pts total)",
        "",
    ]

    for criterion in rubric.criteria:
        lines.append(f"### {criterion.name} (max {criterion.points} pts)")
        for level in criterion.levels:
            lines.append(f"  {level.range[0]}–{level.range[1]} pts: {level.description}")
        lines.append("")

    lines += [
        "---",
        "OUTPUT FORMAT",
        "",
        "Return a JSON object. No prose, no markdown fences, no explanation — raw JSON only.",
        "",
        "Schema:",
        '  {"criteria": [{"name": "<criterion name>", "score": <integer>, "reasoning": "<one sentence>"}]}',
        "",
        "Requirements:",
        f"  - The array must contain exactly {len(rubric.criteria)} entries, one per criterion, in this order: "
        + ", ".join(f'"{n}"' for n in criterion_names),
        "  - Each score must be an integer within the range shown for that criterion",
        "  - Each name must match the criterion name exactly (case-sensitive)",
        "  - Reasoning must be one concise sentence explaining the score",
    ]

    return "\n".join(lines)


def _parse_response(raw: str, rubric: Rubric) -> EvaluationResult:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    data = json.loads(text)
    criteria_map = {c.name: c for c in rubric.criteria}

    criteria_scores = []
    for entry in data["criteria"]:
        ref = criteria_map.get(entry["name"])
        criteria_scores.append(CriterionScore(
            name=entry["name"],
            score=entry["score"],
            max_score=ref.points if ref else 0,
            reasoning=entry["reasoning"],
        ))

    return EvaluationResult(
        criteria_scores=criteria_scores,
        total_score=sum(c.score for c in criteria_scores),
        max_score=rubric.total,
    )


def _average_evaluations(evaluations: List[EvaluationResult]) -> EvaluationResult:
    n = len(evaluations)
    avg_criteria = []
    for i, crit in enumerate(evaluations[0].criteria_scores):
        avg_score = round(sum(e.criteria_scores[i].score for e in evaluations) / n)
        reasonings = " | ".join(e.criteria_scores[i].reasoning for e in evaluations)
        avg_criteria.append(CriterionScore(
            name=crit.name,
            score=avg_score,
            max_score=crit.max_score,
            reasoning=f"avg of {n} judges: {reasonings}",
        ))
    return EvaluationResult(
        criteria_scores=avg_criteria,
        total_score=sum(c.score for c in avg_criteria),
        max_score=evaluations[0].max_score,
    )


def evaluate_output(
    client: anthropic.Anthropic,
    judge_model: str,
    judge_temperature: float,
    judge_max_tokens: int,
    rubric: Rubric,
    output: str,
    num_judges: int = 1,
) -> EvaluationResult:
    system_prompt = _build_system_prompt(rubric)
    evaluations = []

    for _ in range(num_judges):
        response = client.messages.create(
            model=judge_model,
            max_tokens=judge_max_tokens,
            temperature=judge_temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": f"OUTPUT TO EVALUATE:\n\n{output}"}],
        )
        evaluations.append(_parse_response(response.content[0].text, rubric))

    return evaluations[0] if num_judges == 1 else _average_evaluations(evaluations)
