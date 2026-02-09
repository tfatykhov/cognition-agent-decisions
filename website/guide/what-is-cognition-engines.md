# What is Cognition Engines?

Cognition Engines is a decision intelligence platform for AI agents. It helps agents make better decisions by learning from past choices.

## The Problem

AI agents make hundreds of decisions per session - architecture choices, tool selections, process changes, bug fix approaches. But they:

- **Don't learn from past decisions** - each session starts fresh
- **Can't search their history** - "what worked last time?" has no answer
- **Lack guardrails** - nothing prevents repeating known mistakes
- **Have no calibration** - confidence estimates are unchecked guesses

## The Solution

Cognition Engines provides three capabilities:

### 1. Accelerators
Cross-agent learning via semantic decision search. Before making a new decision, query the corpus to find similar past decisions and their outcomes.

```bash
cstp.py query "handling transient API failures" --bridge-side function --top 5
```

### 2. Guardrails
Policy enforcement that prevents violations before they occur. Define rules like "no production changes without code review" and the system enforces them automatically.

```bash
cstp.py check -d "deploy to production" -s high -f 0.85
```

### 3. Auto-Capture
Every decision automatically gets:
- **Deliberation traces** - which queries and checks preceded this decision
- **Bridge-definitions** - structure (what it looks like) + function (what it solves)
- **Related decisions** - linked predecessors from pre-decision queries

## Theoretical Foundation

Cognition Engines is inspired by Marvin Minsky's *Society of Mind*:

- **Ch 12 - Bridge-Definitions:** Describe concepts by both form and purpose
- **Ch 18 - Parallel Bundles:** Seek multiple independent reasons, not one serial chain
- **Ch 27 - Censors:** Proactive warnings that intercept before mistakes, not just reactive blocks
- **Ch 28 - Mental Currencies:** Confidence scores that preserve reasoning structure

## What It's Not

- **Not a database** - it's an intelligence layer on top of storage
- **Not an LLM** - it doesn't generate decisions, it helps agents make better ones
- **Not a logging system** - decisions are indexed, searchable, and connected
