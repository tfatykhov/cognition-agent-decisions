"""Data models for CSTP dashboard."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Reason:
    """A reason supporting a decision."""
    
    type: str  # authority, analogy, analysis, pattern, intuition
    text: str
    strength: float = 0.8


@dataclass
class ProjectContext:
    """Project context for a decision."""
    
    project: str | None = None  # owner/repo format
    feature: str | None = None
    pr: int | None = None
    file: str | None = None
    line: int | None = None
    commit: str | None = None


@dataclass
class Decision:
    """A decision record from CSTP."""
    
    id: str
    summary: str
    category: str
    stakes: str
    confidence: float
    created_at: datetime
    context: str | None = None
    reasons: list[Reason] = field(default_factory=list)
    outcome: str | None = None
    actual_result: str | None = None
    lessons: str | None = None
    reviewed_at: datetime | None = None
    project_context: ProjectContext | None = None
    agent_id: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Create Decision from API response dict.
        
        Args:
            data: Dictionary from CSTP API response.
            
        Returns:
            Decision instance.
        """
        # Parse reasons
        reasons: list[Reason] = []
        for r in data.get("reasons", []):
            if isinstance(r, dict):
                reasons.append(Reason(
                    type=r.get("type", "analysis"),
                    text=r.get("text", ""),
                    strength=float(r.get("strength", 0.8)),
                ))
        
        # Parse project context
        project_context: ProjectContext | None = None
        if pc := data.get("project_context"):
            project_context = ProjectContext(
                project=pc.get("project"),
                feature=pc.get("feature"),
                pr=int(pc["pr"]) if pc.get("pr") else None,
                file=pc.get("file"),
                line=int(pc["line"]) if pc.get("line") else None,
                commit=pc.get("commit"),
            )
        
        # Parse timestamps
        created_at = datetime.fromisoformat(
            data["created_at"].replace("Z", "+00:00")
        )
        reviewed_at: datetime | None = None
        if data.get("reviewed_at"):
            reviewed_at = datetime.fromisoformat(
                data["reviewed_at"].replace("Z", "+00:00")
            )
        
        return cls(
            id=data["id"],
            summary=data.get("summary", data.get("decision", "")),
            category=data.get("category", ""),
            stakes=data.get("stakes", "medium"),
            confidence=float(data.get("confidence", 0.5)),
            created_at=created_at,
            context=data.get("context"),
            reasons=reasons,
            outcome=data.get("outcome"),
            actual_result=data.get("actual_result"),
            lessons=data.get("lessons"),
            reviewed_at=reviewed_at,
            project_context=project_context,
            agent_id=data.get("agent_id"),
        )
    
    @property
    def outcome_icon(self) -> str:
        """Return emoji icon for outcome status."""
        if not self.outcome:
            return "⏳"
        icons = {
            "success": "✅",
            "partial": "⚠️", 
            "failure": "❌",
            "abandoned": "🚫",
        }
        return icons.get(self.outcome, "❓")
    
    @property
    def confidence_pct(self) -> int:
        """Return confidence as percentage."""
        return int(self.confidence * 100)


@dataclass
class CategoryStats:
    """Calibration stats for a category."""
    
    category: str
    total: int
    reviewed: int
    accuracy: float
    brier_score: float
    
    @property
    def accuracy_pct(self) -> int:
        """Return accuracy as percentage."""
        return int(self.accuracy * 100)


@dataclass
class CalibrationStats:
    """Overall calibration statistics from CSTP."""
    
    total_decisions: int
    reviewed_decisions: int
    brier_score: float
    accuracy: float
    interpretation: str
    by_category: list[CategoryStats] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    # F014: Rolling window metadata
    window: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationStats":
        """Create from CSTP API response.
        
        Args:
            data: Dictionary from cstp.getCalibration response.
            
        Returns:
            CalibrationStats instance.
        """
        overall = data.get("overall", {})
        
        # Parse category breakdown
        by_category: list[CategoryStats] = []
        for c in data.get("by_category", []):
            by_category.append(CategoryStats(
                category=c["category"],
                total=c["total_decisions"],
                reviewed=c["reviewed_decisions"],
                accuracy=float(c.get("accuracy", 0.0)),
                brier_score=float(c.get("brier_score", 0.0)),
            ))
        
        # Parse recommendations
        recommendations = [r["message"] for r in data.get("recommendations", [])]
        
        return cls(
            total_decisions=overall.get("total_decisions", overall.get("totalDecisions", 0)),
            reviewed_decisions=overall.get("reviewed_decisions", overall.get("reviewedDecisions", 0)),
            brier_score=float(overall.get("brier_score", overall.get("brierScore", 0.0))),
            accuracy=float(overall.get("accuracy", 0.0)),
            interpretation=overall.get("interpretation", "unknown"),
            by_category=by_category,
            recommendations=recommendations,
            # F014: Rolling window metadata
            window=overall.get("window"),
            period_start=overall.get("period_start", overall.get("periodStart")),
            period_end=overall.get("period_end", overall.get("periodEnd")),
        )
    
    @property
    def accuracy_pct(self) -> int:
        """Return accuracy as percentage."""
        return int(self.accuracy * 100)
    
    @property
    def pending_decisions(self) -> int:
        """Return count of decisions pending review."""
        return self.total_decisions - self.reviewed_decisions
    
    @property
    def calibration_icon(self) -> str:
        """Return emoji based on calibration status."""
        icons = {
            "well_calibrated": "✅",
            "overconfident": "📈",
            "underconfident": "📉",
            "unknown": "❓",
        }
        return icons.get(self.interpretation, "❓")
