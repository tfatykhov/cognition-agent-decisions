# F016 Implementation Plan: Confidence Variance Tracking

**Spec:** `docs/features/V0.9.0-FEATURES.md`  
**Skill:** python-pro  
**Complexity:** Low (~1 hour)

---

## Overview

Track confidence distribution to detect habituation — when agents always use the same confidence (e.g., always 85%) instead of varying based on actual uncertainty.

---

## API Changes

### Enhanced `cstp.getCalibration` Response

Add `confidenceStats` to the response:

```json
{
  "overall": { ... },
  "confidenceStats": {
    "mean": 0.82,
    "stdDev": 0.08,
    "min": 0.60,
    "max": 0.95,
    "count": 45,
    "bucketCounts": {
      "0.5-0.6": 5,
      "0.6-0.7": 12,
      "0.7-0.8": 8,
      "0.8-0.9": 15,
      "0.9-1.0": 5
    }
  },
  "recommendations": [
    {
      "type": "low_variance",
      "message": "80% of decisions use 80-90% confidence. Consider varying more based on actual uncertainty.",
      "severity": "info"
    }
  ]
}
```

---

## Implementation Steps

### Phase 1: Backend (30 min)

#### Step 1.1: Add ConfidenceStats dataclass (10 min)

**File:** `a2a/cstp/calibration_service.py`

```python
@dataclass
class ConfidenceStats:
    """Statistics about confidence distribution."""
    
    mean: float
    std_dev: float
    min_conf: float
    max_conf: float
    count: int
    bucket_counts: dict[str, int]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": round(self.mean, 3),
            "stdDev": round(self.std_dev, 3),
            "min": round(self.min_conf, 2),
            "max": round(self.max_conf, 2),
            "count": self.count,
            "bucketCounts": self.bucket_counts,
        }
```

#### Step 1.2: Add calculate_confidence_stats function (15 min)

```python
def calculate_confidence_stats(decisions: list[dict[str, Any]]) -> ConfidenceStats | None:
    """Calculate confidence distribution statistics.
    
    Args:
        decisions: List of decision data with 'confidence' field.
        
    Returns:
        ConfidenceStats or None if no decisions.
    """
    confidences = [d.get("confidence", 0.5) for d in decisions if "confidence" in d]
    
    if not confidences:
        return None
    
    n = len(confidences)
    mean = sum(confidences) / n
    variance = sum((c - mean) ** 2 for c in confidences) / n
    std_dev = variance ** 0.5
    
    # Bucket counts
    buckets = {"0.5-0.6": 0, "0.6-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
    for c in confidences:
        if c < 0.6:
            buckets["0.5-0.6"] += 1
        elif c < 0.7:
            buckets["0.6-0.7"] += 1
        elif c < 0.8:
            buckets["0.7-0.8"] += 1
        elif c < 0.9:
            buckets["0.8-0.9"] += 1
        else:
            buckets["0.9-1.0"] += 1
    
    return ConfidenceStats(
        mean=mean,
        std_dev=std_dev,
        min_conf=min(confidences),
        max_conf=max(confidences),
        count=n,
        bucket_counts=buckets,
    )
```

#### Step 1.3: Add variance recommendations (5 min)

```python
def generate_variance_recommendations(stats: ConfidenceStats) -> list[CalibrationRecommendation]:
    """Generate recommendations based on confidence variance."""
    recs = []
    
    # Low variance warning
    if stats.std_dev < 0.05 and stats.count >= 10:
        # Find dominant bucket
        max_bucket = max(stats.bucket_counts, key=stats.bucket_counts.get)
        max_pct = stats.bucket_counts[max_bucket] / stats.count * 100
        
        if max_pct > 70:
            recs.append(CalibrationRecommendation(
                type="low_variance",
                message=f"{max_pct:.0f}% of decisions use {max_bucket} confidence. Consider varying more based on actual uncertainty.",
                severity="info",
            ))
    
    # Always high confidence
    if stats.mean > 0.85 and stats.min_conf > 0.75:
        recs.append(CalibrationRecommendation(
            type="overconfident_habit",
            message="All decisions have high confidence (>75%). Are you calibrating to actual uncertainty?",
            severity="warning",
        ))
    
    return recs
```

#### Step 1.4: Integrate into get_calibration (5 min)

Update `GetCalibrationResponse` and `get_calibration()` to include confidence stats.

---

### Phase 2: Dashboard (15 min)

#### Step 2.1: Update models.py

Add `confidence_stats` field to `CalibrationStats`.

#### Step 2.2: Update calibration.html

Display confidence distribution as a simple bar chart or table.

---

### Phase 3: Tests (15 min)

```python
def test_calculate_confidence_stats():
    """Test confidence stats calculation."""
    decisions = [
        {"confidence": 0.85},
        {"confidence": 0.80},
        {"confidence": 0.90},
    ]
    stats = calculate_confidence_stats(decisions)
    assert stats.mean == pytest.approx(0.85, 0.01)
    assert stats.count == 3

def test_low_variance_recommendation():
    """Test low variance generates recommendation."""
    # All decisions at 0.85
    stats = ConfidenceStats(
        mean=0.85, std_dev=0.02, min_conf=0.82, max_conf=0.88,
        count=20, bucket_counts={"0.8-0.9": 20, ...}
    )
    recs = generate_variance_recommendations(stats)
    assert any(r.type == "low_variance" for r in recs)
```

---

## Checklist

| # | Task | Est. | Status |
|---|------|------|--------|
| 1 | Add ConfidenceStats dataclass | 10m | ⬜ |
| 2 | Add calculate_confidence_stats() | 15m | ⬜ |
| 3 | Add generate_variance_recommendations() | 5m | ⬜ |
| 4 | Integrate into get_calibration | 5m | ⬜ |
| 5 | Update dashboard models | 5m | ⬜ |
| 6 | Update calibration template | 10m | ⬜ |
| 7 | Add tests | 10m | ⬜ |
| 8 | Create PR + review | 15m | ⬜ |

**Total:** ~1 hour

---

## Detection Thresholds

| Condition | Alert |
|-----------|-------|
| std_dev < 0.05 AND >70% in one bucket | "low_variance" info |
| mean > 0.85 AND min > 0.75 | "overconfident_habit" warning |
