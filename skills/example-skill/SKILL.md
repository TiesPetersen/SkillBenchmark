---
name: example-skill
description: Incident postmortem writing skill. Use when writing a postmortem, incident report, or post-incident review after a service outage or degradation.
license: MIT
metadata:
  author: SkillBenchmark
  version: "1.0"
---

> **Replace this with your own skill.** This is an example included to demonstrate the expected format.

# Incident Postmortem Writer

You write thorough, blameless incident postmortems. Every postmortem you write must include the following five sections in this order:

## Required structure

### 1. Executive Summary
3–5 sentences. Cover: severity (P0/P1/P2), affected service(s), total duration, and user/business impact. Write it so a non-technical stakeholder can understand the full picture without reading further.

### 2. Timeline
A chronological list of events with precise timestamps (UTC). Every key event must appear: first symptom, alert/page, investigation start, root cause identified, mitigation applied, full resolution. Format each entry as:
`HH:MM UTC — [what happened]`

### 3. Root Cause Analysis
Explain the full causation chain — not just the proximate cause, but why it happened. Work through at least two levels of "why". Be specific: name the exact component, query, config, or code change responsible.

### 4. Impact
Quantify everything you can: duration, number of users or transactions affected, services degraded, SLA implications. If exact numbers are not available, give a best estimate with a range.

### 5. Action Items
A table or list of at least 3 specific, concrete follow-up items. Each must have:
- **What**: the exact task (not "improve monitoring" — "add alerting on connection pool saturation > 80%")
- **Owner**: team or role responsible
- **Due**: target completion date or timeframe

Write in a blameless tone. Focus on systems and processes, not individuals.
