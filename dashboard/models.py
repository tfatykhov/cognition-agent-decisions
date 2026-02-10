"""Data models for CSTP dashboard."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
class DeliberationStep:
    """A step in the deliberation trace."""
    
    step: int
    thought: str
    type: str | None = None
    timestamp: str | None = None
    conclusion: bool = False


@dataclass
class Deliberation:
    """Full deliberation trace for a decision."""
    
    steps: list[DeliberationStep] = field(default_factory=list)
    total_duration_ms: int | None = None
    convergence_score: float | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Deliberation":
        """Create from API response."""
        steps = []
        for s in data.get("steps", []):
            steps.append(DeliberationStep(
                step=s.get("step", 0),
                thought=s.get("thought", ""),
                type=s.get("type"),
                timestamp=s.get("timestamp"),
                conclusion=s.get("conclusion", False),
            ))
        return cls(
            steps=steps,
            total_duration_ms=data.get("total_duration_ms"),
            convergence_score=data.get("convergence_score"),
        )


@dataclass
class Bridge:
    """Bridge definition (structure + function)."""
    
    structure: str | None = None
    function: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bridge":
        """Create from API response."""
        return cls(
            structure=data.get("structure"),
            function=data.get("function"),
        )


@dataclass
class RelatedDecision:
    """A related decision reference."""
    
    id: str
    summary: str
    relationship: str = ""
    distance: float = 0.0


@dataclass
class QualityBreakdown:
    """Quality score with component breakdown."""
    
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityBreakdown":
        """Create from API response."""
        return cls(
            score=float(data.get("score", 0.0)),
            components=data.get("components", {}),
            suggestions=data.get("suggestions", []),
        )


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
    tags: list[str] = field(default_factory=list)
    pattern: str | None = None
    quality_score: float | None = None
    deliberation: Deliberation | None = None
    bridge: Bridge | None = None
    related: list[RelatedDecision] = field(default_factory=list)
    quality: QualityBreakdown | None = None
    
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
            pr_val: int | None = None
            if pc.get("pr"):
                try:
                    pr_val = int(pc["pr"])
                except (ValueError, TypeError):
                    pr_val = None
            line_val: int | None = None
            if pc.get("line"):
                try:
                    line_val = int(pc["line"])
                except (ValueError, TypeError):
                    line_val = None
            project_context = ProjectContext(
                project=pc.get("project"),
                feature=pc.get("feature"),
                pr=pr_val,
                file=pc.get("file"),
                line=line_val,
                commit=pc.get("commit"),
            )
        
        # Parse timestamps - handle both 'created_at' and 'date' field names
        created_str = data.get("created_at") or data.get("date") or ""
        created_at: datetime
        if created_str:
            try:
                # Handle date-only format (YYYY-MM-DD) vs full ISO format
                if len(created_str) == 10:
                    created_at = datetime.fromisoformat(created_str + "T00:00:00+00:00")
                else:
                    # Ensure timezone-aware: replace Z with +00:00, add +00:00 if missing
                    ts = created_str.replace("Z", "+00:00")
                    if "+" not in ts and ts.count("-") <= 2:
                        ts = ts + "+00:00"
                    created_at = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                created_at = datetime.now(UTC)
        else:
            created_at = datetime.now(UTC)
        
        reviewed_at: datetime | None = None
        if data.get("reviewed_at"):
            try:
                ts = data["reviewed_at"].replace("Z", "+00:00")
                if "+" not in ts and ts.count("-") <= 2:
                    ts = ts + "+00:00"
                reviewed_at = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                reviewed_at = None
        
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
            tags=data.get("tags", []),
            pattern=data.get("pattern"),
            quality_score=float(data["quality"]["score"]) if data.get("quality", {}).get("score") else None,
            deliberation=Deliberation.from_dict(data["deliberation"]) if data.get("deliberation") else None,
            bridge=Bridge.from_dict(data["bridge"]) if data.get("bridge") else None,
            related=[
                RelatedDecision(
                    id=r.get("id", ""),
                    summary=r.get("title", r.get("summary", "")),
                    relationship=r.get("relationship", ""),
                    distance=float(r.get("distance", 0.0)),
                )
                for r in data.get("related", [])
            ] or [],
            quality=QualityBreakdown.from_dict(data["quality"]) if data.get("quality") else None,
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
class ConfidenceDistribution:
    """Confidence distribution stats for habituation detection."""
    
    mean: float
    std_dev: float
    min_conf: float
    max_conf: float
    count: int
    bucket_counts: dict[str, int]
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfidenceDistribution":
        """Create from API response."""
        return cls(
            mean=float(data.get("mean", 0.0)),
            std_dev=float(data.get("stdDev", 0.0)),
            min_conf=float(data.get("min", 0.0)),
            max_conf=float(data.get("max", 0.0)),
            count=int(data.get("count", 0)),
            bucket_counts=data.get("bucketCounts", {}),
        )
    
    @property
    def mean_pct(self) -> int:
        """Return mean as percentage."""
        return int(self.mean * 100)


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
    # F016: Confidence variance
    confidence_stats: ConfidenceDistribution | None = None
    
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
        
        # F016: Parse confidence stats
        conf_stats = None
        if cs_data := data.get("confidenceStats"):
            conf_stats = ConfidenceDistribution.from_dict(cs_data)
        
        return cls(
            total_decisions=overall.get(
                "total_decisions", overall.get("totalDecisions", 0)
            ),
            reviewed_decisions=overall.get(
                "reviewed_decisions", overall.get("reviewedDecisions", 0)
            ),
            brier_score=float(
                overall.get("brier_score", overall.get("brierScore", 0.0))
            ),
            accuracy=float(overall.get("accuracy", 0.0)),
            interpretation=overall.get("interpretation", "unknown"),
            by_category=by_category,
            recommendations=recommendations,
            # F014: Rolling window metadata
            window=overall.get("window"),
            period_start=overall.get("period_start", overall.get("periodStart")),
            period_end=overall.get("period_end", overall.get("periodEnd")),
            # F016: Confidence stats
            confidence_stats=conf_stats,
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
