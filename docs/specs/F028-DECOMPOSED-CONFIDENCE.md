# F028: Decomposed Confidence - Per-Reason Confidence Weights

> **Status:** Proposed
> **Source:** Minsky Society of Mind Ch 28 (The Mind and the World, section 28.3)
> **Depends on:** Schema change across dataclass, YAML, CLI, MCP
> **Priority:** Medium (addresses known calibration issue)

## Problem

Our confidence score is a single number (0.0-1.0) that, per Minsky 28.3, "perfectly conceals all traces of its origins." When an agent rates a decision at 0.85, that number hides:
- Which reasons are strong vs weak
- Where uncertainty actually lives
- Why the agent chose that number

This contributes to our low variance problem (stdDev 0.049) - agents collapse rich reasoning into a narrow band of scores.

## Concept

Each reason gets its own confidence weight:

```yaml
reasons:
  - type: empirical
    text: "Similar pattern succeeded in order-service"
    confidence: 0.95    # Strong - direct evidence
  - type: analysis
    text: "Backoff handles transient failures"
    confidence: 0.80    # Moderate - theoretical
  - type: intuition
    text: "Feels like the right approach"
    confidence: 0.50    # Low - gut feeling

confidence: 0.82  # Weighted aggregate (computed or manual)
```

## Benefits

1. **Preserves structure** - the reasoning behind the number is visible
2. **Better calibration** - can track which *reason types at which confidence levels* predict success
3. **Natural variance** - per-reason scores will spread out even when aggregates cluster
4. **Richer analytics** - "your empirical reasons at 0.90+ are well-calibrated, but your analysis reasons at 0.80 are overconfident"

## Schema Changes

### Reason dataclass
```python
@dataclass
class Reason:
    type: str           # existing
    text: str           # existing
    confidence: float   # NEW - optional, 0.0-1.0
```

### Aggregation options
- **Manual override**: Agent sets overall confidence explicitly (current behavior, preserved)
- **Weighted average**: Auto-compute from per-reason confidences
- **Min-of-reasons**: Overall confidence = weakest reason (conservative)

### CLI
```bash
uv run scripts/cstp.py record \
  -d "my decision" \
  -f 0.85 \
  -r "empirical:direct evidence from prod:0.95" \
  -r "analysis:theoretical reasoning:0.70"
```

### MCP
```json
{
  "reasons": [
    {"type": "empirical", "text": "...", "confidence": 0.95},
    {"type": "analysis", "text": "...", "confidence": 0.70}
  ]
}
```

## Backward Compatibility

- `confidence` field on reasons is optional (defaults to null)
- Overall `confidence` field unchanged
- Existing decisions unaffected
- Analytics only activate when per-reason confidence data exists

## Key Insight from Minsky

> "Whenever we turn to measurements, we forfeit some uses of intellect. Currencies and magnitudes help us make comparisons only by concealing the differences among what they purport to represent."

> "Add five and eight to make thirteen, and tell that answer to a friend: thirteen will be all your friend can know, since no amount of ingenious thought can ever show that it came from adding five and eight!"

## Related Decisions

- `4fe7b03d` - Initial Ch 28 analysis
- `ee4c12be` - P2 finding on inconsistent reason types
- `b02d10ba` - Adopted Ch 18 parallel bundles (multiple independent reasons)

## Activation Criteria

- Build when specifically addressing the low-variance calibration issue
- Or when reason-type stats (`cstp.getReasonStats`) show actionable patterns worth decomposing
