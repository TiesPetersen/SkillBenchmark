# SkillBenchmark

**Objective benchmarking for Agent Skills (SKILL.md files).** Measures whether a skill actually improves LLM output quality — and by how much — using blind judge evaluation and confidence intervals.

> Thousands of Agent Skills exist across public registries. There is no systematic way to know whether any of them actually work. SkillBenchmark fills that gap.

---

## The problem

An Agent Skill is only as good as the improvement it produces. Right now, skill authors publish based on intuition, and users install based on anecdote. There is no objective way to answer:

- Does this skill improve output quality — and by how much?
- Does it do so consistently, or only on certain task types?
- Is the quality improvement worth the extra token cost?

---

## How it works

SkillBenchmark runs each task N times. Each run produces two outputs: one from the LLM without any skill, one with the skill injected as a system prompt. Both outputs are then passed independently to a judge LLM that scores them against a rubric — without knowing which is which, and without ever seeing the original task prompt. After all runs, confidence intervals are computed over the scores for each condition and compared to produce a verdict.

**Blind evaluation** removes author bias. The judge receives only the output and the rubric — never the task prompt, never any indication of which condition produced the output.

**Confidence intervals** (t-distribution) determine the verdict:
- `SKILL BETTER` — with-skill CI is entirely above without-skill CI
- `BASELINE BETTER` — without-skill CI is entirely above with-skill CI
- `INCONCLUSIVE` — CIs overlap (increase runs for more signal)

**Token cost** is tracked per run as a first-class metric alongside quality scores.

---

## Quickstart

```bash
git clone https://github.com/your-username/SkillBenchmark
cd SkillBenchmark
pip install -r requirements.txt
cp .env.example .env
```

Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Drop your skill into `skills/` and point `config.yml` at it:
```yaml
skill_path: skills/my-skill/SKILL.md
```

Add your tasks to `tasks/` — each task is a YAML file with a prompt and a scoring rubric. An example task is included to get you started. The more tasks you add, the more meaningful the benchmark results will be.

Run the benchmark:
```bash
python run.py
```

Results are written to `results/` as both a JSON log and a markdown report.

---

## Project structure

```
SkillBenchmark/
├── tasks/                          # One YAML file per task
│   └── example_task.yml
├── skills/                         # One folder per skill (Agent Skills standard)
│   └── example-skill/
│       └── SKILL.md
├── results/                        # Output (gitignored)
├── src/
│   ├── config.py                   # Config loader
│   ├── task.py                     # Task YAML parser
│   ├── runner.py                   # LLM runner (with/without skill)
│   ├── evaluator.py                # Blind judge scoring
│   ├── stats.py                    # Confidence interval calculation
│   ├── report.py                   # JSON + markdown reporter
│   └── main.py                     # Orchestrator
├── run.py                          # Entry point
├── config.yml                      # Configuration
└── .env.example                    # Example environment variables (copy to .env and fill in)
```

---

## Configuration

All settings live in `config.yml`:

```yaml
number_of_runs_per_task: 3
number_of_judges_per_run: 1

runner_model: claude-sonnet-4-6
runner_temperature: 0.7
runner_max_tokens: 4096

judge_model: claude-sonnet-4-6
judge_temperature: 0.0
judge_max_tokens: 1024

skill_path: skills/my-skill/SKILL.md
tasks_dir: tasks
results_dir: results
confidence_level: 0.95
```

**`number_of_runs_per_task`** — How many times each task is run in full (both with and without skill). Each run is an independent sample. More runs produce tighter confidence intervals and more reliable verdicts, but cost more tokens. Use 3 during development and 10+ before drawing real conclusions.

**`number_of_judges_per_run`** — How many times the judge LLM scores each output. Multiple judges average out scoring inconsistency. 1 is fine for quick tests; use 3 for important benchmarks.

**`runner_model`** — The model used to complete the tasks. This is what you're measuring the skill's effect on.

**`runner_temperature`** — Controls how varied the runner's outputs are between runs. Higher values (e.g. 0.7) produce more diverse outputs across runs, which is what you want — it gives the benchmark more signal to work with. Setting this to 0 would produce nearly identical outputs every run, making multiple runs pointless.

**`runner_max_tokens`** — The maximum length of the runner's output. Increase this for tasks that require long responses (documents, code files). The right value depends on your task — too low and the output gets cut off mid-response.

**`judge_model`** — The model used to score outputs. Using a different model than the runner reduces the risk of one model systematically favouring its own style of output.

**`judge_temperature`** — Controls how consistent the judge's scores are. Keep this at 0 so the judge produces deterministic, repeatable scores rather than varying scores for the same output.

**`judge_max_tokens`** — The maximum length of the judge's response. The judge only returns structured JSON, so 1024 is almost always sufficient.

**`confidence_level`** — The confidence level used for the confidence intervals (e.g. 0.95 = 95% CI). Higher values produce wider intervals and make it harder to reach a non-inconclusive verdict, but the verdict is more trustworthy when you do.

**`skill_path`** — Path to the `SKILL.md` file to benchmark.

**`tasks_dir`** / **`results_dir`** — Where to read tasks from and write results to.

---

## Writing tasks

Tasks live in `tasks/` as YAML files. Each file defines the prompt given to the runner LLM and a scoring rubric given only to the judge — they are kept separate so the judge cannot reverse-engineer which output was "helped".

```yaml
name: "Write an incident postmortem"
version: "1.0"

task:
  context: |
    You are a senior engineer at a tech company. An incident has just been
    resolved and you need to write the official postmortem report.
  description: |
    Write a complete postmortem for the following incident:
    [incident description here]

rubric:
  context: |
    A good postmortem is specific, actionable, and structured. It should
    allow any engineer who was not present to fully understand what happened,
    why, and what will be done to prevent recurrence.
  criteria:
    - name: Timeline
      points: 20
      levels:
        - range: [0, 8]
          description: "No timeline, or a vague narrative without specific times."
        - range: [9, 14]
          description: "Timeline present but incomplete or uses approximate times."
        - range: [15, 20]
          description: "Chronological timeline with precise timestamps covering all key events."

    - name: Root cause analysis
      points: 25
      levels:
        - range: [0, 10]
          description: "Root cause missing, vague, or incorrect."
        - range: [11, 18]
          description: "Root cause identified but causation chain is incomplete."
        - range: [19, 25]
          description: "Full causation chain explained across at least two levels of why."

    # ... more criteria, summing to 100 pts total
```

**Task design tips:**
- The rubric should reward exactly what the skill claims to improve — this is what creates a measurable delta
- Each criterion's levels should be clearly distinguishable so the judge produces consistent scores
- The `context` in the rubric gives the judge background without revealing the task prompt

---

## Using skills

Skills follow the [Agent Skills open standard](https://agentskills.io), compatible with Claude Code, Cursor, Gemini CLI, GitHub Copilot, and others.

Each skill lives in its own folder under `skills/`:

```
skills/
└── my-skill/
    └── SKILL.md
```

`SKILL.md` format:

```markdown
---
name: my-skill
description: What this skill does and when to use it.
license: MIT
metadata:
  author: your-name
  version: "1.0"
---

# Skill instructions here

Everything below the frontmatter becomes the system prompt for the runner LLM.
```

The frontmatter `name` and `description` fields are standard Agent Skills metadata. The markdown body is what gets injected as the system prompt — frontmatter is stripped automatically.

---

## Reading results

Each run produces two files in `results/`:

**`benchmark_<skill>_<task>_<timestamp>.md`** — human-readable summary:

```
# Benchmark — Write an incident postmortem
Skill: `my-skill` | 2026-05-26 17:30:02

Verdict: SKILL BETTER

| | With skill | Without skill |
|---|---|---|
| Mean score    | 91.4 / 100        | 74.2 / 100        |
| Std dev       | 3.1               | 6.8               |
| 95% CI        | [88.5, 94.3]      | [67.9, 80.5]      |
| Runs          | 10                | 10                |

Criterion breakdown (mean across runs):
| Criterion          | With skill | Without skill | Max |
|--------------------|------------|---------------|-----|
| Timeline           | 18.9       | 12.1          | 20  |
| Root cause         | 23.1       | 17.4          | 25  |
| ...
```

**`benchmark_<skill>_<task>_<timestamp>.json`** — full run log with every output, per-criterion score, reasoning, and token count for reproducibility.

---

## Philosophy

**Blind evaluation over subjective preference.**
The judge never knows which output used the skill. This mirrors how rigorous AI benchmarks work and removes author bias from results.

**Relative improvement over absolute scores.**
The goal is not a universal quality score. It is to measure the delta a specific skill produces on a specific category of tasks.

**Token cost is a first-class metric.**
Quality improvements that come at disproportionate token cost are not free. Every run logs token usage for both conditions.

**Reproducibility over impressiveness.**
Every prompt, output, score, and reasoning is stored in the JSON log. Nothing is hidden.

---

## Limitations

- **Text output only (v1).** Agentic / file-writing runs are not yet supported.
- **Claude API only (v1).** Multi-provider support is planned.
- **Small N = wide CIs.** With 3 runs, confidence intervals are wide. Use 10+ runs before drawing conclusions.
- **Judge consistency.** A single LLM judge can be inconsistent. Use `number_of_judges_per_run: 3` to average out variance for important benchmarks.

---

## License

MIT — see [LICENSE](LICENSE). Built by [Ties Petersen](https://github.com/tiespetersen).
