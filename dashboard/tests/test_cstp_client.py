"""Tests for CSTP client."""
from datetime import datetime, timezone

from dashboard.models import CalibrationStats, CategoryStats, Decision, Reason


def test_decision_from_dict() -> None:
    """Test Decision.from_dict parsing."""
    data = {
        "id": "abc123",
        "summary": "Test decision",
        "category": "architecture",
        "stakes": "medium",
        "confidence": 0.85,
        "created_at": "2026-02-05T12:00:00Z",
        "context": "Some context",
        "reasons": [
            {"type": "analysis", "text": "Because reasons", "strength": 0.9}
        ],
    }
    
    decision = Decision.from_dict(data)
    
    assert decision.id == "abc123"
    assert decision.summary == "Test decision"
    assert decision.confidence == 0.85
    assert decision.confidence_pct == 85
    assert len(decision.reasons) == 1
    assert decision.reasons[0].type == "analysis"
    assert decision.outcome_icon == "⏳"


def test_decision_outcome_icons() -> None:
    """Test outcome icon mapping."""
    decision = Decision(
        id="test",
        summary="test",
        category="test",
        stakes="low",
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
    )
    
    assert decision.outcome_icon == "⏳"
    
    decision.outcome = "success"
    assert decision.outcome_icon == "✅"
    
    decision.outcome = "partial"
    assert decision.outcome_icon == "⚠️"
    
    decision.outcome = "failure"
    assert decision.outcome_icon == "❌"


def test_calibration_stats_from_dict() -> None:
    """Test CalibrationStats.from_dict parsing."""
    data = {
        "overall": {
            "total_decisions": 100,
            "reviewed_decisions": 50,
            "brier_score": 0.05,
            "accuracy": 0.9,
            "interpretation": "well_calibrated",
        },
        "by_category": [
            {
                "category": "architecture",
                "total_decisions": 30,
                "reviewed_decisions": 20,
                "accuracy": 0.95,
                "brier_score": 0.03,
            }
        ],
        "recommendations": [
            {"message": "Great work!"}
        ],
    }
    
    stats = CalibrationStats.from_dict(data)
    
    assert stats.total_decisions == 100
    assert stats.reviewed_decisions == 50
    assert stats.pending_decisions == 50
    assert stats.accuracy_pct == 90
    assert stats.calibration_icon == "✅"
    assert len(stats.by_category) == 1
    assert stats.by_category[0].category == "architecture"
    assert len(stats.recommendations) == 1
