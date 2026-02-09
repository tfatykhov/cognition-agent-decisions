# Decision Protocol

The core workflow that every agent follows. Record early, update as you go.

## The Five Steps

### Step 1: Query Similar Decisions

Before making a decision, search the corpus for similar past choices.

```bash
# Semantic search
cstp.py query "handling transient API failures" --top 5

# Directional search (Minsky Ch 12)
cstp.py query "the problem" --bridge-side function --top 5   # What solved this?
cstp.py query "the pattern" --bridge-side structure --top 5  # Where was this used?
```

### Step 2: Check Guardrails

Validate your planned action against policy rules.

```bash
cstp.py check -d "deploy retry logic to production" -s high -f 0.85
```

If blocked, the response tells you why and what to fix.

### Step 3: Record the Decision (immediately)

Log your intent right away. This captures the deliberation trace from steps 1-2.

```bash
cstp.py record \
  -d "Plan: Add exponential backoff with jitter" \
  -f 0.85 \
  -c architecture \
  -s medium \
  -r "analysis:Backoff handles transient failures" \
  -r "empirical:Similar pattern succeeded in order-service" \
  --tag retry --tag resilience \
  --pattern "Use exponential backoff for transient external failures"
```

**Record now, update later.** Save the returned decision ID.

### Step 4: Think During Work

Capture your reasoning as you work. Each thought appends to the decision's deliberation trace.

```bash
cstp.py think --id <decision_id> "Exploring constant vs exponential backoff"
cstp.py think --id <decision_id> "Exponential with jitter prevents thundering herd"
```

### Step 5: Update When Done

Finalize the decision with what you actually did.

```bash
cstp.py update <decision_id> \
  -d "Added exponential backoff with jitter for API retries" \
  --context "Implemented in retry_handler.py. Max 3 retries, base 1s, jitter +/-25%."
```

## What Happens Automatically

When you follow query -> check -> record, four features fire:

| Feature | What It Does | Response Field |
|---------|-------------|----------------|
| **Deliberation Traces** | Links your queries, checks, and reasoning to the decision | `deliberation_auto: true` |
| **Bridge-Definitions** | Extracts structure/function from your text | `bridge_auto: true` |
| **Related Decisions** | Links decisions found in queries | `related_count: N` |
| **Quality Score** | Measures recording completeness (0.0-1.0) | `quality.score` |

## Why Record Early?

Deliberation inputs (queries, checks, thoughts) accumulate per agent. When you call `record`, the server attaches them and clears the tracker. If you wait too long:

- Inputs from one decision bleed into the next
- Quality drops because deliberation is missing
- The trace doesn't reflect your actual process

Recording early with `"Plan: ..."` captures everything, then `update` refines it.

## Tags and Patterns

Every decision should include:

- **Tags** (`--tag`): Reusable keywords for filtering. Examples: `caching`, `security`, `api`, `config`.
- **Pattern** (`--pattern`): The abstract principle. "Use stateless infrastructure for horizontal scaling" — not "Used Redis".

Think at two levels: what you *did* (operational) and what *principle* it represents (conceptual).

## Reason Types

Use at least 2 different types for robustness (Minsky Ch 18 - parallel bundles):

| Type | When to Use |
|------|------------|
| `analysis` | Logical reasoning about the problem |
| `empirical` | Based on observed data or past results |
| `pattern` | Matches a known successful pattern |
| `authority` | Expert or documentation says so |
| `constraint` | Required by technical/policy limits |
| `analogy` | Similar to another domain's solution |
| `intuition` | Gut feeling (use sparingly, be honest) |
| `elimination` | Other options ruled out |

## Review Outcomes

Later, when you know the result:

```bash
cstp.py review --id abc123 --outcome success --result "Retry logic reduced 503s by 95%"
```

This builds calibration data. Your Brier score improves as you review more decisions.
