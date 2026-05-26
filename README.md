# SkillBenchmark

**Benchmarking for Agent Skills (SKILL.md files).** Measures whether a skill actually improves LLM output quality, and by how much, using blind judge evaluation and confidence intervals.

> Thousands of Agent Skills exist across public registries. There is no systematic way to know whether any of them actually work. SkillBenchmark fills that gap.

---

## The problem

An Agent Skill is only as good as the improvement it produces. Right now, skill authors publish based on intuition, and users install based on anecdote. There is no objective way to answer:

- Does this skill improve output quality, and by how much?
- Does it do so consistently, or only on certain task types?
- Is the quality improvement worth the extra token cost?

---

## How it works

SkillBenchmark runs each task N times. Each run produces two outputs: one from the LLM without any skill, one with the skill injected as a system prompt. Both outputs are then passed independently to a judge LLM that scores them against a rubric, without knowing which is which, and without ever seeing the original task prompt. After all runs, confidence intervals are computed over the scores for each condition and compared to produce a verdict.

**Blind evaluation** removes author bias. The judge receives only the output and the rubric, never the task prompt, never any indication of which condition produced the output.

**On LLM-as-judge reliability:** any individual LLM judge can be inconsistent or biased. SkillBenchmark mitigates this in two ways: (1) the same judge scores both conditions under identical prompting, so systematic bias cancels out in the comparison — what matters is the *relative* score, not the absolute value; (2) using multiple judges per run and averaging their scores reduces random variance. The rubric is the main lever for quality — clear, distinguishable scoring levels produce more consistent results than vague ones.

**Confidence intervals** (t-distribution, displayed as mean ± margin) quantify the uncertainty. Non-overlapping CIs indicate a statistically meaningful difference between conditions; overlapping CIs indicate the effect is too uncertain to call — add more runs to tighten them.

**Token cost** is tracked per run as a first-class metric alongside quality scores. Note: includes the tokens needed to include the skill in the system prompt.

> **Current scope:** SkillBenchmark currently evaluates skills on raw text LLM calls: single-turn prompt-in, response-out. This covers a large class of skills but misses skills that are designed to guide multi-step agent behaviour. The next major milestone is full agent environment support: sandboxed tool-use runs where a skill's effect on multi-turn, agentic tasks can be measured end-to-end. If you're interested in contributing or have ideas about what that should look like, reach out on [LinkedIn](https://linkedin.com/in/tiespetersen) :)

---

## Quickstart

```bash
git clone https://github.com/TiesPetersen/SkillBenchmark
cd SkillBenchmark
pip install -r requirements.txt
cp .env.example .env
```

Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

The repo ships with a working example — the [Caveman skill](#example-benchmark-caveman) and three tasks are already in `tasks/` and `skills/`, and `config.yml` points at them. You can run `python run.py` immediately to see real output before touching anything.

When you're ready to benchmark your own skill, drop it into `skills/` and update `config.yml`:
```yaml
skill_path: skills/my-skill/SKILL.md
```

Then replace or extend the tasks in `tasks/` with tasks relevant to your skill. The more tasks you add, the more meaningful the results will be (see [Writing Tasks](#writing-tasks)).

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
│   ├── caveman_debug_explanation.yml       # Example: explain a Python bug to a developer
│   ├── caveman_user_error_message.yml      # Example: write a user-facing error message
│   └── caveman_commit_message.yml          # Example: write a commit message for a diff
├── skills/                         # One folder per skill (Agent Skills standard)
│   └── caveman/                    # Example: Caveman skill
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
judge_temperature: 0.1
judge_max_tokens: 1024

skill_path: skills/my-skill/SKILL.md
tasks_dir: tasks
results_dir: results
confidence_level: 0.95
```

**`number_of_runs_per_task`** — How many times each task is run in full (both with and without skill). Each run is an independent sample. More runs produce tighter confidence intervals and more reliable verdicts, but cost more tokens. Use 3 during development and 10+ before drawing real conclusions.

**`number_of_judges_per_run`** — How many times the judge LLM scores each output. Multiple judges average out scoring inconsistency. 1 is fine for quick tests; use 3+ for important benchmarks.

**`runner_model`** — The model used to complete the tasks. This is what you're measuring the skill's effect on.

**`runner_temperature`** — Controls how varied the runner's outputs are between runs. Higher values (e.g. 0.7) produce more diverse outputs across runs, which is what you want — it gives the benchmark more signal to work with. Setting this to 0 would produce nearly identical outputs every run, making multiple runs pointless.

**`runner_max_tokens`** — The maximum length of the runner's output. Increase this for tasks that require long responses (documents, code files). The right value depends on your task — too low and the output gets cut off mid-response.

**`judge_model`** — The model used to score outputs. Using a different model than the runner reduces the risk of one model systematically favouring its own style of output.

**`judge_temperature`** — Controls how consistent the judge's scores are. Keep this at 0.0-0.2 so the judge produces deterministic, repeatable scores rather than varying scores for the same output.

**`judge_max_tokens`** — The maximum length of the judge's response. The judge only returns structured JSON, so 1024 is almost always sufficient.

**`confidence_level`** — The confidence level used for the confidence intervals (e.g. 0.95 = 95% CI). Higher values produce wider intervals, but the result is more trustworthy when CIs don't overlap.

**`skill_path`** — Path to the `SKILL.md` file to benchmark.

**`tasks_dir`** / **`results_dir`** — Where to read tasks from and write results to.

---

## Writing tasks

Tasks live in `tasks/` as YAML files. Each file defines the prompt given to the runner LLM and a scoring rubric given only to the judge. They are kept separate so the judge cannot reverse-engineer which output was "helped".

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

    # ... more criteria
```

**Task design tips:**
- The rubric should be written generically enough, so that the LLM using the skill doesn't have an advantage, because the rubric is focused on exactly what the skill is designed to improve. For example, if the skill is designed to help with structured output, the rubric should reward good structure but not explicitly call out "used the exact format from the skill instructions".
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

**`<task_slug>.md`** — human-readable summary:

```
# Write an incident postmortem
*Skill: `my-skill` | 2026-05-26 17:30:02*

## Score summary

| | With skill | Without skill |
|---|---|---|
| Mean score          | 91.4 / 100   | 74.2 / 100   |
| 95% CI              | 91.4 ± 2.9   | 74.2 ± 5.5   |
| Delta (95% CI)      | +17.2 ± 6.2  | —            |
| Std dev             | 3.1          | 6.8          |
| Samples (runs × judges) | 10      | 10           |

## Criterion breakdown (mean across runs)
| Criterion     | With skill | Without skill | Max |
|---|---|---|---|
| Timeline      | 18.9       | 12.1          | 20  |
| Root cause    | 23.1       | 17.4          | 25  |
| ...
```

**`benchmark_<skill>_<task>_<timestamp>.json`** — full run log with every output, per-criterion score, reasoning, and token count for reproducibility.

---

## Example benchmark: Caveman

The `tasks/` and `skills/` folders include a ready-to-run example that benchmarks the [Caveman skill](https://github.com/JuliusBrussee/caveman) by Julius Brussee. Caveman is a popular Agent Skill that makes an LLM respond in compressed, fragment-based prose to cut output token usage by roughly 65–75% while claiming to maintain technical accuracy.

> **Note:** This is not a rigorous or definitive evaluation of Caveman. It is a small illustrative example using three tasks and a small number of runs, intended only to show how SkillBenchmark works in practice. Treat the results as a demonstration, not a verdict on the skill.
>
> Full credit for the Caveman skill goes to [Julius Brussee](https://github.com/JuliusBrussee/caveman) — it is not part of this project and is included here solely as a benchmark subject.

The three example tasks were chosen to probe different contexts where Caveman's terse style might help, hurt, or have no effect:

| Task | Hypothesis |
|---|---|
| Explain a Python bug to a developer | Caveman-style fragments are acceptable for dev-to-dev communication — skill may help or be neutral |
| Write a user-facing error message | Non-technical users need full sentences and clear tone — skill likely hurts |
| Write a commit message for a diff | Commit messages reward brevity and precision — skill may help |

### Results

**Run config:** 5 runs × 3 judges = 15 samples per condition · `claude-haiku-4-5` runner and judge · 95% CI

| Task | With skill | Without skill | Delta | Avg tokens (with / without skill) |
|---|---|---|---|---|
| Write a commit message | 93.5 ± 1.5 | 89.9 ± 2.3 | +3.6 ± 2.8 | 1896 / 952 |
| Explain a Python bug | 99.5 ± 0.5 | 100.0 ± 0.0 | −0.5 ± 0.5 | 1551 / 729 |
| Write a user-facing error message | 89.7 ± 3.2 | 87.7 ± 2.5 | +2.0 ± 4.0 | 1233 / 306 |

The CI intervals on all three tasks overlap, so no difference is statistically confirmed at 95%. The extra token cost across all tasks is roughly the size of the SKILL.md being injected as system prompt (~950 tokens), with output length largely unchanged.

<details>
<summary>Criterion breakdown — Write a commit message</summary>

| Criterion | With skill | Without skill | Max |
|---|---|---|---|
| Conventional Commits format | 24.3 | 24.2 | 25 |
| Accuracy — what changed | 33.7 | 32.4 | 35 |
| Explains the why | 22.3 | 20.8 | 25 |
| Conciseness | 13.3 | 12.5 | 15 |

</details>

<details>
<summary>Criterion breakdown — Explain a Python bug</summary>

| Criterion | With skill | Without skill | Max |
|---|---|---|---|
| Root cause accuracy | 40.0 | 40.0 | 40 |
| Fix correctness | 34.9 | 35.0 | 35 |
| Clarity for a developer | 24.6 | 25.0 | 25 |

</details>

<details>
<summary>Criterion breakdown — Write a user-facing error message</summary>

| Criterion | With skill | Without skill | Max |
|---|---|---|---|
| Clarity for a non-technical user | 28.0 | 28.0 | 30 |
| Actionability | 25.5 | 23.9 | 30 |
| Tone | 17.7 | 17.7 | 20 |
| Structure and completeness | 18.5 | 18.1 | 20 |

</details>

---

## Limitations

- **Text output only (v1).** Agentic / file-writing runs are not yet supported.
  > Help wanted! If you have ideas or want to contribute, reach out on [LinkedIn](https://linkedin.com/in/tiespetersen).
- **Claude API only (v1).** Multi-provider support is planned if there's interest.
  > If you'd like to see support for your model of choice, let me know on [LinkedIn](https://linkedin.com/in/tiespetersen) or open an issue. If enough people want it, it'll move up the priority list.

---

## License

MIT — see [LICENSE](LICENSE). Built by [Ties Petersen](https://github.com/tiespetersen) ([Linkedin](https://linkedin.com/in/tiespetersen))
