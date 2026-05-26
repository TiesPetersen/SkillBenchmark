# SkillBenchmark

Objectively measure whether an Agent Skill (SKILL.md) improves LLM output quality.

Runs your tasks with and without a skill, scores both outputs with a blind judge LLM, and reports the quality delta with confidence intervals.

## How it works

1. Define tasks in `tasks/` as YAML files — each with a prompt and a scoring rubric
2. Point it at a `skill.md` file
3. The runner calls the LLM N times with and without the skill injected into the system prompt
4. A separate judge LLM scores each output blindly against the rubric — it never sees the task prompt or which condition produced the output
5. Each rubric criterion is scored independently with a points range and level descriptors; scores aggregate to a 0–100 total
6. After all runs, confidence intervals are computed (t-distribution) for both conditions
7. A verdict is produced: **skill better**, **baseline better**, or **inconclusive** — based on whether the CIs overlap
8. Results are written as a JSON log and a markdown report to `results/`

The blind judging design removes author bias: the judge has no way to favour the skill-assisted output.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
```

Edit `config.yml` to set your model, number of runs, and skill path.

## Usage

```bash
python run.py
```

## Task format

Each file in `tasks/` is a YAML with a prompt and a structured rubric:

```yaml
name: "My task"
version: 1

task: |
  Your prompt here...
  
rubric:
  total: 100
  criteria:
    - name: Criterion name
      points: 25
      levels:
        - range: [20, 25]
          label: Excellent
          description: "..."
```

## Output

| File | Contents |
|------|----------|
| `results/benchmark_<skill>_<timestamp>.json` | Full run log — outputs, scores, token counts |
| `results/benchmark_<skill>_<timestamp>.md`   | Summary report with verdict and score tables |

## License

MIT — see [LICENSE](LICENSE).
