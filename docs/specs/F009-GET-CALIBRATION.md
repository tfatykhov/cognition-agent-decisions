# F009: Get Calibration Endpoint

| Field | Value |
|-------|-------|
| Feature ID | F009 |
| Status | Implemented |
| Priority | P1 |
| Depends On | F008 (Review Decision) |
| Blocks | None |
| Decision | 30d70c34 |

---

## Summary

Add `cstp.getCalibration` JSON-RPC method to retrieve confidence calibration statistics, enabling agents to understand their decision-making accuracy and adjust future confidence levels.

## Goals

1. Calculate Brier scores for reviewed decisions
2. Break down accuracy by confidence level
3. Identify over/under-confidence patterns
4. Filter by category, stakes, time range
5. Provide actionable recommendations

## Non-Goals

- Real-time calibration updates (batch calculation)
- Cross-agent calibration comparison (future)
- Automatic confidence adjustment (agent decides)

---

## API Specification

### Method

`cstp.getCalibration`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.getCalibration",
  "params": {
    "filters": {
      "agent": "emerson",
      "category": "architecture",
      "minDecisions": 5,
      "since": "2026-01-01"
    },
    "groupBy": "confidenceBucket"
  },
  "id": 1
}
```

### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filters` | object | ❌ | Filter criteria |
| `filters.agent` | string | ❌ | Filter by agent ID (from `recorded_by`) |
| `filters.category` | string | ❌ | Filter by category |
| `filters.stakes` | string | ❌ | Filter by stakes level |
| `filters.since` | string | ❌ | ISO date, only decisions after |
| `filters.until` | string | ❌ | ISO date, only decisions before |
| `filters.minDecisions` | int | ❌ | Minimum decisions for stats (default: 5) |
| `groupBy` | string | ❌ | Group by: `confidenceBucket`, `category`, `stakes`, `agent` |

### Response (Success)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "overall": {
      "brierScore": 0.18,
      "accuracy": 0.72,
      "totalDecisions": 45,
      "reviewedDecisions": 38,
      "calibrationGap": -0.08,
      "interpretation": "slightly_overconfident"
    },
    "byConfidenceBucket": [
      {
        "bucket": "0.9-1.0",
        "decisions": 12,
        "successRate": 0.75,
        "expectedRate": 0.95,
        "gap": -0.20,
        "interpretation": "overconfident"
      },
      {
        "bucket": "0.7-0.9",
        "decisions": 18,
        "successRate": 0.78,
        "expectedRate": 0.80,
        "gap": -0.02,
        "interpretation": "well_calibrated"
      },
      {
        "bucket": "0.5-0.7",
        "decisions": 8,
        "successRate": 0.62,
        "expectedRate": 0.60,
        "gap": 0.02,
        "interpretation": "well_calibrated"
      }
    ],
    "recommendations": [
      {
        "type": "confidence_adjustment",
        "message": "When you feel 90%+ confident, outcomes suggest ~75%. Consider 75-80% instead.",
        "severity": "warning"
      },
      {
        "type": "strength",
        "message": "Your 70-90% confidence range is well calibrated. Trust this range.",
        "severity": "info"
      }
    ],
    "queryTime": "2026-02-12T14:30:00Z"
  },
  "id": 1
}
```

### Response (Insufficient Data)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "overall": null,
    "byConfidenceBucket": [],
    "recommendations": [
      {
        "type": "insufficient_data",
        "message": "Only 3 reviewed decisions. Need at least 5 for calibration stats.",
        "severity": "info"
      }
    ],
    "queryTime": "2026-02-12T14:30:00Z"
  },
  "id": 1
}
```

---

## Calibration Metrics

### Brier Score
Measures prediction accuracy. Lower is better.

```
Brier = (1/N) × Σ(confidence - outcome)²

Where outcome = 1 for success, 0 for failure
```

| Brier Score | Interpretation |
|-------------|----------------|
| 0.00 - 0.10 | Excellent calibration |
| 0.10 - 0.20 | Good calibration |
| 0.20 - 0.30 | Fair calibration |
| 0.30+ | Poor calibration |

### Calibration Gap
Difference between stated confidence and actual success rate.

```
Gap = actual_success_rate - average_confidence

Positive = underconfident (better than you think)
Negative = overconfident (worse than you think)
```

### Confidence Buckets
Group decisions by confidence level:
- `0.9-1.0`: High confidence
- `0.7-0.9`: Moderate-high
- `0.5-0.7`: Moderate
- `0.0-0.5`: Low confidence

---

## Implementation Plan

### Phase 1: Data Collection (~1h)

#### 1.1 Add get_reviewed_decisions function

```python
async def get_reviewed_decisions(
    decisions_path: str | None = None,
    agent: str | None = None,
    category: str | None = None,
    stakes: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Get all reviewed decisions matching filters."""
    base = Path(decisions_path or DECISIONS_PATH)
    decisions = []
    
    for yaml_file in base.rglob("*-decision-*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        # Filter: must be reviewed with outcome
        if data.get("status") != "reviewed":
            continue
        if "outcome" not in data:
            continue
        
        # Apply filters
        if agent and data.get("recorded_by") != agent:
            continue
        if category and data.get("category") != category:
            continue
        if stakes and data.get("stakes") != stakes:
            continue
        if since and data.get("date", "") < since:
            continue
        if until and data.get("date", "") > until:
            continue
        
        decisions.append(data)
    
    return decisions
```

### Phase 2: Calibration Calculation (~2h)

#### 2.1 Add calibration models

```python
@dataclass
class ConfidenceBucket:
    bucket: str
    decisions: int
    success_rate: float
    expected_rate: float
    gap: float
    interpretation: str

@dataclass
class CalibrationResult:
    brier_score: float
    accuracy: float
    total_decisions: int
    reviewed_decisions: int
    calibration_gap: float
    interpretation: str

@dataclass
class CalibrationRecommendation:
    type: str
    message: str
    severity: str  # info, warning, error
```

#### 2.2 Add calculate_calibration function

```python
def calculate_calibration(decisions: list[dict]) -> CalibrationResult | None:
    """Calculate calibration metrics from reviewed decisions."""
    if len(decisions) < 5:
        return None
    
    outcomes = []
    confidences = []
    
    for d in decisions:
        confidence = d.get("confidence", 0.5)
        outcome = 1.0 if d.get("outcome") == "success" else 0.0
        
        # Partial success = 0.5
        if d.get("outcome") == "partial":
            outcome = 0.5
        
        outcomes.append(outcome)
        confidences.append(confidence)
    
    # Brier score
    brier = sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / len(decisions)
    
    # Accuracy (binary: success or not)
    accuracy = sum(1 for o in outcomes if o >= 0.5) / len(decisions)
    
    # Calibration gap
    avg_confidence = sum(confidences) / len(confidences)
    gap = accuracy - avg_confidence
    
    # Interpretation
    if abs(gap) < 0.05:
        interpretation = "well_calibrated"
    elif gap < -0.10:
        interpretation = "overconfident"
    elif gap < 0:
        interpretation = "slightly_overconfident"
    elif gap > 0.10:
        interpretation = "underconfident"
    else:
        interpretation = "slightly_underconfident"
    
    return CalibrationResult(
        brier_score=round(brier, 3),
        accuracy=round(accuracy, 3),
        total_decisions=len(decisions),
        reviewed_decisions=len(decisions),
        calibration_gap=round(gap, 3),
        interpretation=interpretation,
    )
```

#### 2.3 Add bucket analysis

```python
def calculate_buckets(decisions: list[dict]) -> list[ConfidenceBucket]:
    """Calculate calibration by confidence bucket."""
    buckets = {
        "0.9-1.0": {"min": 0.9, "max": 1.0, "decisions": [], "expected": 0.95},
        "0.7-0.9": {"min": 0.7, "max": 0.9, "decisions": [], "expected": 0.80},
        "0.5-0.7": {"min": 0.5, "max": 0.7, "decisions": [], "expected": 0.60},
        "0.0-0.5": {"min": 0.0, "max": 0.5, "decisions": [], "expected": 0.25},
    }
    
    for d in decisions:
        conf = d.get("confidence", 0.5)
        for name, bucket in buckets.items():
            if bucket["min"] <= conf < bucket["max"] or (bucket["max"] == 1.0 and conf == 1.0):
                bucket["decisions"].append(d)
                break
    
    results = []
    for name, bucket in buckets.items():
        if len(bucket["decisions"]) < 3:
            continue
        
        successes = sum(1 for d in bucket["decisions"] if d.get("outcome") == "success")
        success_rate = successes / len(bucket["decisions"])
        gap = success_rate - bucket["expected"]
        
        if abs(gap) < 0.10:
            interpretation = "well_calibrated"
        elif gap < 0:
            interpretation = "overconfident"
        else:
            interpretation = "underconfident"
        
        results.append(ConfidenceBucket(
            bucket=name,
            decisions=len(bucket["decisions"]),
            success_rate=round(success_rate, 2),
            expected_rate=bucket["expected"],
            gap=round(gap, 2),
            interpretation=interpretation,
        ))
    
    return results
```

### Phase 3: Recommendations (~1h)

```python
def generate_recommendations(
    overall: CalibrationResult | None,
    buckets: list[ConfidenceBucket],
) -> list[CalibrationRecommendation]:
    """Generate actionable recommendations."""
    recs = []
    
    if overall is None:
        recs.append(CalibrationRecommendation(
            type="insufficient_data",
            message="Need at least 5 reviewed decisions for calibration.",
            severity="info",
        ))
        return recs
    
    # Overall calibration feedback
    if overall.interpretation == "overconfident":
        recs.append(CalibrationRecommendation(
            type="confidence_adjustment",
            message=f"You're overconfident by {abs(overall.calibration_gap)*100:.0f}%. Consider lowering confidence estimates.",
            severity="warning",
        ))
    elif overall.interpretation == "underconfident":
        recs.append(CalibrationRecommendation(
            type="confidence_adjustment",
            message=f"You're underconfident by {overall.calibration_gap*100:.0f}%. Trust yourself more.",
            severity="info",
        ))
    
    # Bucket-specific feedback
    for bucket in buckets:
        if bucket.interpretation == "overconfident" and bucket.gap < -0.15:
            recs.append(CalibrationRecommendation(
                type="bucket_warning",
                message=f"At {bucket.bucket} confidence, actual success is {bucket.success_rate*100:.0f}%. Adjust to ~{bucket.success_rate*100:.0f}%.",
                severity="warning",
            ))
    
    # Strength recognition
    well_calibrated = [b for b in buckets if b.interpretation == "well_calibrated"]
    if well_calibrated:
        ranges = ", ".join(b.bucket for b in well_calibrated)
        recs.append(CalibrationRecommendation(
            type="strength",
            message=f"Well calibrated in {ranges} range. Trust these estimates.",
            severity="info",
        ))
    
    return recs
```

### Phase 4: Dispatcher Integration (~30m)

```python
async def _handle_get_calibration(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    filters = params.get("filters", {})
    
    decisions = await get_reviewed_decisions(
        category=filters.get("category"),
        stakes=filters.get("stakes"),
        since=filters.get("since"),
        until=filters.get("until"),
    )
    
    min_decisions = filters.get("minDecisions", 5)
    
    overall = calculate_calibration(decisions) if len(decisions) >= min_decisions else None
    buckets = calculate_buckets(decisions)
    recommendations = generate_recommendations(overall, buckets)
    
    return {
        "overall": overall.to_dict() if overall else None,
        "byConfidenceBucket": [b.to_dict() for b in buckets],
        "recommendations": [r.to_dict() for r in recommendations],
        "queryTime": datetime.now(UTC).isoformat(),
    }

dispatcher.register("cstp.getCalibration", _handle_get_calibration)
```

### Phase 5: Tests (~1h)

**Test cases:**
- Calibration with sufficient data
- Insufficient data response
- Filter by category
- Bucket calculations
- Recommendation generation
- Edge cases (all success, all failure)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `a2a/cstp/calibration_service.py` | Create | Calibration calculation logic |
| `a2a/cstp/decision_service.py` | Modify | Add get_reviewed_decisions |
| `a2a/cstp/dispatcher.py` | Modify | Register new method |
| `tests/test_calibration_service.py` | Create | Unit tests |
| `tests/test_f009_get_calibration.py` | Create | Integration tests |

---

## Integration with Decision Flow

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│   recordDecision ──▶ reviewDecision ──▶ getCalibration     │
│        │                    │                  │           │
│        ▼                    ▼                  ▼           │
│   "confidence: 0.85"   "outcome: success"   "Brier: 0.18"  │
│                                                 │           │
│                                                 ▼           │
│   ◀─────────────────────────────────────────────           │
│   Next decision: "Similar decisions had 72% success.       │
│                   Your 85% confidence may be high."        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Estimated Effort

| Phase | Time |
|-------|------|
| Data Collection | 1h |
| Calibration Calculation | 2h |
| Recommendations | 1h |
| Dispatcher Integration | 30m |
| Tests | 1h |
| **Total** | **~5.5h** |

---

## Future Enhancements

- **Category-specific calibration**: "You're overconfident in architecture but well-calibrated in process"
- **Trend analysis**: "Your calibration improved 15% this month"
- **Cross-agent comparison**: "Your Brier score is better than 70% of agents"
- **Active nudging**: Inject calibration warnings into queryDecisions responses
