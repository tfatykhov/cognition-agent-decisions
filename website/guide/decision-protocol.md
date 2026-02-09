# Decision Protocol

The core workflow that every agent follows. The server auto-captures everything.

## The Three Steps

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

### Step 3: Record the Decision

Log what you decided, why, and with what confidence.

```bash
cstp.py record \
  -d "Added exponential backoff with jitter" \
  -f 0.85 \
  -c architecture \
  -s medium \
  -r "analysis:Backoff handles transient failures" \
  -r "empirical:Similar pattern succeeded in order-service"
```

## What Happens Automatically

When you follow query -> check -> record, three features fire:

| Feature | What It Does | Response Field |
|---------|-------------|----------------|
| **Deliberation Traces** | Links your queries and checks to the decision | `deliberation_auto: true` |
| **Bridge-Definitions** | Extracts structure/function from your text | `bridge_auto: true` |
| **Related Decisions** | Links decisions found in queries | `related_count: N` |

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
