# CSTP Workflows

This document describes how CSTP integrates into development workflows.

## Overview

CSTP (Cognition State Transfer Protocol) creates a feedback loop for AI agent decisions. Two primary workflows benefit from this integration:

1. **Developer Agent Workflow** — Making and tracking development decisions
2. **Code Review Agent Workflow** — Learning from review patterns over time

---

## 1. Developer Agent Workflow

### Phase 1: Planning (Before Coding)

When facing an architectural or implementation decision:

```
Agent thinks: "Should I use async or sync for this API endpoint?"
```

**Step 1: Query similar past decisions**
```json
{
  "method": "cstp.queryDecisions",
  "params": {
    "query": "async vs sync API implementation",
    "top": 5
  }
}
```

Returns past decisions with outcomes:
- 3 async API decisions: 2 success (high-traffic), 1 failure (overkill for CRUD)
- Pattern emerges: "async wins when >100 req/s expected"

**Step 2: Check guardrails**
```json
{
  "method": "cstp.checkGuardrails",
  "params": {
    "context": { "stakes": "medium", "confidence": 0.8 }
  }
}
```

**Step 3: Record the decision**
```json
{
  "method": "cstp.recordDecision",
  "params": {
    "summary": "Use sync for /users endpoint - low traffic CRUD",
    "confidence": 0.85,
    "category": "architecture",
    "stakes": "medium",
    "reasons": [
      { "type": "precedent", "text": "async overkill for simple CRUD" },
      { "type": "analysis", "text": "<50 req/s expected" }
    ]
  }
}
```

### Phase 2: Implementation (During Coding)

Log smaller decisions inline as you code:

```json
{ "summary": "Use Pydantic for validation over manual checks", "confidence": 0.9 }
{ "summary": "Add retry logic with exponential backoff", "confidence": 0.75 }
```

### Phase 3: Post-Merge (Outcome Tracking)

After deployment, when outcome is known:

```json
{
  "method": "cstp.reviewDecision",
  "params": {
    "id": "abc123",
    "outcome": "success",
    "actualResult": "Endpoint handles load fine, no async needed",
    "lessons": "Trust the traffic estimates"
  }
}
```

### Phase 4: Calibration (Weekly)

Check decision-making accuracy:

```json
{
  "method": "cstp.getCalibration",
  "params": {
    "filters": { "category": "architecture" }
  }
}
```

Response:
```json
{
  "overall": {
    "brierScore": 0.12,
    "calibrationGap": -0.05,
    "interpretation": "slightly_overconfident"
  },
  "recommendations": [
    { "message": "At 90%+ confidence, actual success is 82%. Consider 85% instead." }
  ]
}
```

---

## 2. Code Review Agent Workflow

### The Problem

Code review agents are typically stateless:
- Forget everything after each review
- Can't learn from past mistakes
- No way to track which findings were actually valuable

### The Solution: CSTP-Enhanced Code Review

```
┌─────────────────────────────────────────────────────────────┐
│                    CODE REVIEW AGENT                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. RECEIVE PR                                               │
│     ↓                                                        │
│  2. QUERY PAST REVIEWS                                       │
│     cstp.queryDecisions("code review findings for Python")   │
│     → "Last 5 reviews: missed error handling 3 times"        │
│     → "Pattern: async code often has unclosed resources"     │
│     ↓                                                        │
│  3. FOCUSED REVIEW                                           │
│     Prioritize checking known weak spots                     │
│     ↓                                                        │
│  4. RECORD REVIEW DECISIONS                                  │
│     cstp.recordDecision(                                     │
│       summary="Flagged missing error handler in api.py:42",  │
│       confidence=0.9,                                        │
│       category="code-review"                                 │
│     )                                                        │
│     ↓                                                        │
│  5. POST FINDINGS TO PR                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Query Before Reviewing

Before reviewing a PR, the agent queries past review patterns:

```json
{
  "method": "cstp.queryDecisions",
  "params": {
    "query": "code review patterns Python API",
    "filters": { "category": "code-review" },
    "top": 10
  }
}
```

This reveals:
- Common issues missed in past reviews
- False positives that wasted time
- Patterns specific to the codebase

### Step 2: Record Each Finding

Each significant finding becomes a tracked decision:

```json
{
  "method": "cstp.recordDecision",
  "params": {
    "summary": "P1: Missing error handler for database connection in api.py:42",
    "confidence": 0.9,
    "category": "code-review",
    "stakes": "high",
    "context": "PR #8 cognition-agent-decisions"
  }
}
```

### Step 3: Track Outcomes

When the reviewed code reaches production:

**If bug found (review was correct):**
```json
{
  "method": "cstp.reviewDecision",
  "params": {
    "id": "finding-123",
    "outcome": "success",
    "actualResult": "Bug found in production, review was correct to flag"
  }
}
```

**If bug slipped through (review missed it):**
```json
{
  "method": "cstp.recordDecision",
  "params": {
    "summary": "Missed null check in user validation",
    "outcome": "failure",
    "lessons": "Should have checked edge case for empty input"
  }
}
```

**If finding was false positive:**
```json
{
  "method": "cstp.reviewDecision",
  "params": {
    "id": "finding-456",
    "outcome": "failure",
    "actualResult": "Code was actually correct, wasted developer time"
  }
}
```

### Step 4: Reviewer Calibration

Weekly calibration check for the review agent:

```json
{
  "method": "cstp.getCalibration",
  "params": {
    "filters": {
      "agent": "CodeReviewer",
      "category": "code-review"
    }
  }
}
```

Response:
```json
{
  "overall": {
    "accuracy": 0.78,
    "brierScore": 0.18,
    "interpretation": "slightly_overconfident"
  },
  "byConfidenceBucket": [
    { "bucket": "0.9-1.0", "successRate": 0.95, "interpretation": "well_calibrated" },
    { "bucket": "0.7-0.9", "successRate": 0.65, "interpretation": "overconfident" }
  ],
  "recommendations": [
    { "message": "P1 findings are 95% accurate - trust these", "severity": "info" },
    { "message": "P3 findings are only 45% valid - reconsider flagging", "severity": "warning" }
  ]
}
```

### The Meta-Learning Loop

```
CodeReviewer reviews code
       ↓
Records decisions about findings
       ↓
Production validates findings
       ↓
Outcomes recorded
       ↓
Calibration analyzed
       ↓
CodeReviewer adjusts focus ←───┘
```

**Result:** A code review agent that:
- Improves over time
- Focuses on what actually matters
- Stops wasting time on false positives
- Learns codebase-specific patterns

---

## Integration Example

### Spawning a CSTP-Enhanced Code Reviewer

```python
sessions_spawn(
    label="code-reviewer",
    model="gemini-3-pro-high",
    thinking="high",
    task="""
    Review PR #8 at https://github.com/owner/repo/pull/8
    
    BEFORE REVIEWING:
    1. Query similar past reviews:
       cstp.queryDecisions("code review findings for Python APIs")
    2. Note patterns from past outcomes
    
    DURING REVIEW:
    3. Check for known weak spots first
    4. Record each P1/P2 finding as a decision with cstp.recordDecision
    
    AFTER REVIEW:
    5. Post findings to PR
    
    Sign as '🔍 CodeReviewer'
    """
)
```

---

## Benefits

| Without CSTP | With CSTP |
|--------------|-----------|
| Stateless reviews | Learns from history |
| No outcome tracking | Knows what worked |
| Same mistakes repeated | Patterns recognized |
| No calibration | Confidence adjusted over time |
| Generic focus | Codebase-specific priorities |

---

## Flow Diagram

See `docs/images/cstp-flow-diagram.png` for visual representation.
