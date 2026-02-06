# F015 Implementation Plan: Calibration Drift Alerts

**Spec:** `docs/specs/V0.9.0-FEATURES.md`  
**Skill:** python-pro  
**Depends on:** F014 (rolling windows)

---

## Overview

Proactive drift detection that compares recent calibration (30d) against historical baseline (90d+) and generates alerts when performance degrades.

---

## API Design

### New Method: `cstp.checkDrift`

**Request:**
```json
{
    "jsonrpc": "2.0",
    "method": "cstp.checkDrift",
    "params": {
        "thresholdBrier": 0.20,      // Alert if Brier degrades >20%
        "thresholdAccuracy": 0.15,   // Alert if accuracy drops >15%
        "category": null,            // Optional category filter
        "project": null              // Optional project filter
    },
    "id": 1
}
```

**Response:**
```json
{
    "driftDetected": true,
    "recent": {
        "window": "30d",
        "brierScore": 0.15,
        "accuracy": 0.75,
        "decisions": 12
    },
    "historical": {
        "window": "90d+",
        "brierScore": 0.08,
        "accuracy": 0.88,
        "decisions": 45
    },
    "alerts": [
        {
            "type": "brier_degradation",
            "category": "architecture",
            "recentValue": 0.15,
            "historicalValue": 0.08,
            "changePct": 87.5,
            "severity": "warning",
            "message": "Architecture decisions: Brier score degraded 88% (0.08 → 0.15)"
        },
        {
            "type": "accuracy_drop",
            "category": "architecture",
            "recentValue": 0.75,
            "historicalValue": 0.88,
            "changePct": -14.8,
            "severity": "warning",
            "message": "Architecture decisions: Accuracy dropped 15% (88% → 75%)"
        }
    ],
    "recommendations": [
        {
            "type": "recalibrate",
            "message": "Consider lowering confidence estimates for architecture decisions",
            "severity": "info"
        }
    ]
}
```

---

## Implementation Steps

### Phase 1: Backend - Core Logic (45 min)

#### Step 1.1: Create drift_service.py (15 min)

**File:** `a2a/cstp/drift_service.py`

```python
"""Drift detection service for CSTP."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .calibration_service import (
    calculate_calibration,
    get_reviewed_decisions,
    window_to_dates,
)


@dataclass
class DriftAlert:
    """A calibration drift alert."""
    
    type: str  # brier_degradation, accuracy_drop
    category: str | None
    recent_value: float
    historical_value: float
    change_pct: float
    severity: str  # info, warning, error
    message: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "category": self.category,
            "recentValue": self.recent_value,
            "historicalValue": self.historical_value,
            "changePct": round(self.change_pct, 1),
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class WindowStats:
    """Stats for a time window."""
    
    window: str
    brier_score: float
    accuracy: float
    decisions: int
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "brierScore": self.brier_score,
            "accuracy": self.accuracy,
            "decisions": self.decisions,
        }


@dataclass
class CheckDriftRequest:
    """Request for drift check."""
    
    threshold_brier: float = 0.20    # 20% degradation
    threshold_accuracy: float = 0.15  # 15% drop
    category: str | None = None
    project: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckDriftRequest":
        return cls(
            threshold_brier=float(data.get("thresholdBrier", 0.20)),
            threshold_accuracy=float(data.get("thresholdAccuracy", 0.15)),
            category=data.get("category"),
            project=data.get("project"),
        )


@dataclass
class CheckDriftResponse:
    """Response with drift detection results."""
    
    drift_detected: bool
    recent: WindowStats | None
    historical: WindowStats | None
    alerts: list[DriftAlert] = field(default_factory=list)
    recommendations: list[dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "driftDetected": self.drift_detected,
            "recent": self.recent.to_dict() if self.recent else None,
            "historical": self.historical.to_dict() if self.historical else None,
            "alerts": [a.to_dict() for a in self.alerts],
            "recommendations": self.recommendations,
        }
```

#### Step 1.2: Implement check_drift function (20 min)

```python
async def check_drift(
    request: CheckDriftRequest,
    decisions_path: str | None = None,
) -> CheckDriftResponse:
    """Check for calibration drift between recent and historical periods.
    
    Compares 30-day window against 90-day+ baseline.
    """
    # Get recent decisions (last 30 days)
    recent_since, recent_until = window_to_dates("30d")
    recent_decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        category=request.category,
        project=request.project,
        since=recent_since,
        until=recent_until,
    )
    
    # Get historical decisions (older than 30 days)
    historical_decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        category=request.category,
        project=request.project,
        until=recent_since,  # Before recent window
    )
    
    # Need minimum decisions for meaningful comparison
    min_decisions = 5
    if len(recent_decisions) < min_decisions or len(historical_decisions) < min_decisions:
        return CheckDriftResponse(
            drift_detected=False,
            recent=None,
            historical=None,
            recommendations=[{
                "type": "insufficient_data",
                "message": f"Need at least {min_decisions} decisions in both periods for drift detection",
                "severity": "info",
            }],
        )
    
    # Calculate calibration for both periods
    recent_cal = calculate_calibration(recent_decisions)
    historical_cal = calculate_calibration(historical_decisions)
    
    if not recent_cal or not historical_cal:
        return CheckDriftResponse(drift_detected=False, recent=None, historical=None)
    
    recent_stats = WindowStats(
        window="30d",
        brier_score=recent_cal.brier_score,
        accuracy=recent_cal.accuracy,
        decisions=len(recent_decisions),
    )
    
    historical_stats = WindowStats(
        window="90d+",
        brier_score=historical_cal.brier_score,
        accuracy=historical_cal.accuracy,
        decisions=len(historical_decisions),
    )
    
    # Detect drift
    alerts = detect_drift_alerts(
        recent_cal,
        historical_cal,
        request.threshold_brier,
        request.threshold_accuracy,
        request.category,
    )
    
    # Generate recommendations
    recommendations = generate_drift_recommendations(alerts)
    
    return CheckDriftResponse(
        drift_detected=len(alerts) > 0,
        recent=recent_stats,
        historical=historical_stats,
        alerts=alerts,
        recommendations=recommendations,
    )
```

#### Step 1.3: Alert detection helpers (10 min)

```python
def detect_drift_alerts(
    recent: Any,  # CalibrationResult
    historical: Any,
    threshold_brier: float,
    threshold_accuracy: float,
    category: str | None,
) -> list[DriftAlert]:
    """Detect calibration drift between periods."""
    alerts: list[DriftAlert] = []
    
    # Check Brier score degradation (higher is worse)
    if historical.brier_score > 0:
        brier_change = (recent.brier_score - historical.brier_score) / historical.brier_score
        if brier_change > threshold_brier:
            alerts.append(DriftAlert(
                type="brier_degradation",
                category=category,
                recent_value=recent.brier_score,
                historical_value=historical.brier_score,
                change_pct=brier_change * 100,
                severity="warning" if brier_change < 0.5 else "error",
                message=f"Brier score degraded {brier_change*100:.0f}% ({historical.brier_score:.2f} → {recent.brier_score:.2f})",
            ))
    
    # Check accuracy drop (lower is worse)
    if historical.accuracy > 0:
        accuracy_change = (historical.accuracy - recent.accuracy) / historical.accuracy
        if accuracy_change > threshold_accuracy:
            alerts.append(DriftAlert(
                type="accuracy_drop",
                category=category,
                recent_value=recent.accuracy,
                historical_value=historical.accuracy,
                change_pct=-accuracy_change * 100,
                severity="warning" if accuracy_change < 0.25 else "error",
                message=f"Accuracy dropped {accuracy_change*100:.0f}% ({historical.accuracy*100:.0f}% → {recent.accuracy*100:.0f}%)",
            ))
    
    return alerts


def generate_drift_recommendations(alerts: list[DriftAlert]) -> list[dict[str, str]]:
    """Generate recommendations based on drift alerts."""
    recommendations: list[dict[str, str]] = []
    
    for alert in alerts:
        if alert.type == "brier_degradation":
            recommendations.append({
                "type": "recalibrate",
                "message": "Consider adjusting confidence estimates - you may be overconfident",
                "severity": "info",
            })
        elif alert.type == "accuracy_drop":
            recommendations.append({
                "type": "review_process",
                "message": "Review recent decisions - accuracy has declined",
                "severity": "info",
            })
    
    return recommendations
```

---

### Phase 2: Dispatcher Integration (15 min)

#### Step 2.1: Register handler in dispatcher.py

```python
from .drift_service import CheckDriftRequest, check_drift

async def _handle_check_drift(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.checkDrift method."""
    request = CheckDriftRequest.from_dict(params)
    response = await check_drift(request)
    return response.to_dict()

# In register_handlers:
dispatcher.register("cstp.checkDrift", _handle_check_drift)
```

---

### Phase 3: Dashboard (30 min)

#### Step 3.1: Add drift check to CSTP client (10 min)

```python
async def check_drift(
    self,
    threshold_brier: float = 0.20,
    threshold_accuracy: float = 0.15,
    category: str | None = None,
) -> dict[str, Any]:
    """Check for calibration drift."""
    params: dict[str, Any] = {
        "thresholdBrier": threshold_brier,
        "thresholdAccuracy": threshold_accuracy,
    }
    if category:
        params["category"] = category
    
    return await self._call("cstp.checkDrift", params)
```

#### Step 3.2: Add drift alerts to calibration page (20 min)

Add a "Check Drift" button and display alerts on the calibration dashboard.

---

### Phase 4: Tests (20 min)

#### Step 4.1: Unit tests for drift detection

```python
def test_detect_drift_brier_degradation():
    """Test Brier score degradation detection."""
    # ... mock recent/historical with significant drift
    
def test_detect_drift_no_drift():
    """Test no alerts when metrics stable."""
    
def test_check_drift_insufficient_data():
    """Test handling of insufficient data."""
```

---

## Checklist

| # | Task | Est. | Status |
|---|------|------|--------|
| 1 | Create `drift_service.py` dataclasses | 15m | ⬜ |
| 2 | Implement `check_drift()` function | 20m | ⬜ |
| 3 | Implement alert detection helpers | 10m | ⬜ |
| 4 | Register in `dispatcher.py` | 10m | ⬜ |
| 5 | Add `check_drift()` to dashboard client | 10m | ⬜ |
| 6 | Add drift UI to calibration template | 20m | ⬜ |
| 7 | Add unit tests | 15m | ⬜ |
| 8 | Create PR + code review | 15m | ⬜ |

**Total:** ~2 hours

---

## Integration with Heartbeat

After F015 ships, agents can call `cstp.checkDrift` during heartbeats:

```python
# In HEARTBEAT.md
drift = await cstp.check_drift()
if drift["driftDetected"]:
    for alert in drift["alerts"]:
        notify_user(alert["message"])
```
