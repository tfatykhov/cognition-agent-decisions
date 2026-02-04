"""
Pattern Detection Engine
Analyzes decision history for patterns, calibration, and anti-patterns.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CalibrationBucket:
    """Confidence bucket for calibration analysis."""
    min_conf: float
    max_conf: float
    decisions: list[dict] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return len(self.decisions)
    
    @property
    def predicted_rate(self) -> float:
        """Average confidence (predicted success rate)."""
        if not self.decisions:
            return 0.0
        return sum(d.get("confidence", 0) for d in self.decisions) / len(self.decisions)
    
    @property
    def actual_rate(self) -> float:
        """Actual success rate based on outcomes."""
        with_outcomes = [d for d in self.decisions if d.get("outcome")]
        if not with_outcomes:
            return 0.0
        successes = sum(1 for d in with_outcomes if d.get("outcome") == "success")
        return successes / len(with_outcomes)
    
    @property
    def brier_score(self) -> float:
        """Brier score for this bucket."""
        with_outcomes = [d for d in self.decisions if d.get("outcome")]
        if not with_outcomes:
            return 0.0
        
        total = 0.0
        for d in with_outcomes:
            conf = d.get("confidence", 0.5)
            actual = 1.0 if d.get("outcome") == "success" else 0.0
            total += (conf - actual) ** 2
        
        return total / len(with_outcomes)
    
    def to_dict(self) -> dict:
        return {
            "range": f"{int(self.min_conf*100)}-{int(self.max_conf*100)}%",
            "count": self.count,
            "predicted": round(self.predicted_rate, 3),
            "actual": round(self.actual_rate, 3),
            "brier": round(self.brier_score, 4),
        }


@dataclass
class CategoryStats:
    """Statistics for a decision category."""
    category: str
    decisions: list[dict] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return len(self.decisions)
    
    @property
    def avg_confidence(self) -> float:
        if not self.decisions:
            return 0.0
        return sum(d.get("confidence", 0) for d in self.decisions) / len(self.decisions)
    
    @property
    def success_rate(self) -> float:
        with_outcomes = [d for d in self.decisions if d.get("outcome")]
        if not with_outcomes:
            return 0.0
        successes = sum(1 for d in with_outcomes if d.get("outcome") == "success")
        return successes / len(with_outcomes)
    
    @property
    def outcomes_count(self) -> int:
        return len([d for d in self.decisions if d.get("outcome")])
    
    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "count": self.count,
            "with_outcomes": self.outcomes_count,
            "avg_confidence": round(self.avg_confidence, 3),
            "success_rate": round(self.success_rate, 3),
        }


@dataclass
class AntiPattern:
    """Detected anti-pattern."""
    pattern_type: str
    description: str
    severity: str  # low, medium, high
    decisions: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "type": self.pattern_type,
            "description": self.description,
            "severity": self.severity,
            "decision_count": len(self.decisions),
            "decisions": [d.get("title", d.get("id", "unknown")) for d in self.decisions[:5]],
        }


class PatternDetector:
    """Analyzes decision history for patterns and insights."""
    
    def __init__(self, decisions: list[dict] = None):
        self.decisions = decisions or []
    
    def load_from_directory(self, directory: Path) -> int:
        """Load decisions from YAML files."""
        self.decisions = []
        
        yaml_files = list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml"))
        
        for path in yaml_files:
            try:
                content = path.read_text()
                data = self._parse_yaml(content)
                if data and isinstance(data, dict):
                    if "decision" in data or "title" in data:
                        data["_source"] = str(path)
                        self.decisions.append(data)
            except Exception:
                pass
        
        return len(self.decisions)
    
    def _parse_yaml(self, content: str) -> dict:
        """Parse YAML content."""
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            pass
        
        # Basic parsing
        result = {}
        for line in content.split('\n'):
            if line.strip().startswith('#'):
                continue
            if ':' in line and not line.startswith(' '):
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                if val:
                    if val.lower() == 'true':
                        result[key] = True
                    elif val.lower() == 'false':
                        result[key] = False
                    elif val.startswith('"') and val.endswith('"'):
                        result[key] = val[1:-1]
                    else:
                        try:
                            result[key] = float(val)
                        except ValueError:
                            result[key] = val
        return result
    
    def calibration_report(self) -> dict:
        """
        Generate calibration report.
        Returns Brier scores and confidence bucket analysis.
        """
        # Create buckets
        buckets = [
            CalibrationBucket(0.0, 0.2),
            CalibrationBucket(0.2, 0.4),
            CalibrationBucket(0.4, 0.6),
            CalibrationBucket(0.6, 0.8),
            CalibrationBucket(0.8, 1.0),
        ]
        
        # Assign decisions to buckets
        for d in self.decisions:
            conf = d.get("confidence", 0.5)
            # Normalize if stored as percentage
            if conf > 1:
                conf = conf / 100
            
            for bucket in buckets:
                if bucket.min_conf <= conf < bucket.max_conf or (bucket.max_conf == 1.0 and conf == 1.0):
                    bucket.decisions.append(d)
                    break
        
        # Calculate overall Brier score
        with_outcomes = [d for d in self.decisions if d.get("outcome")]
        overall_brier = 0.0
        if with_outcomes:
            total = 0.0
            for d in with_outcomes:
                conf = d.get("confidence", 0.5)
                if conf > 1:
                    conf = conf / 100
                actual = 1.0 if d.get("outcome") == "success" else 0.0
                total += (conf - actual) ** 2
            overall_brier = total / len(with_outcomes)
        
        # Interpret Brier score
        if overall_brier < 0.1:
            interpretation = "Excellent calibration"
        elif overall_brier < 0.15:
            interpretation = "Good calibration"
        elif overall_brier < 0.25:
            interpretation = "Fair calibration"
        else:
            interpretation = "Poor calibration - review confidence estimates"
        
        return {
            "total_decisions": len(self.decisions),
            "with_outcomes": len(with_outcomes),
            "overall_brier": round(overall_brier, 4),
            "interpretation": interpretation,
            "buckets": [b.to_dict() for b in buckets if b.count > 0],
        }
    
    def category_analysis(self) -> dict:
        """
        Analyze decisions by category.
        Returns success rates and patterns per category.
        """
        categories: dict[str, CategoryStats] = {}
        
        for d in self.decisions:
            cat = d.get("category", "uncategorized")
            if cat not in categories:
                categories[cat] = CategoryStats(cat)
            categories[cat].decisions.append(d)
        
        # Sort by count
        sorted_cats = sorted(categories.values(), key=lambda c: c.count, reverse=True)
        
        # Identify concerning categories
        concerning = []
        for cat in sorted_cats:
            if cat.outcomes_count >= 3 and cat.success_rate < 0.5:
                concerning.append({
                    "category": cat.category,
                    "success_rate": round(cat.success_rate, 3),
                    "reason": "Low success rate (<50%)",
                })
            elif cat.avg_confidence < 0.5 and cat.count >= 3:
                concerning.append({
                    "category": cat.category,
                    "avg_confidence": round(cat.avg_confidence, 3),
                    "reason": "Low average confidence",
                })
        
        return {
            "total_categories": len(categories),
            "categories": [c.to_dict() for c in sorted_cats],
            "concerning": concerning,
        }
    
    def detect_antipatterns(self) -> dict:
        """
        Detect decision anti-patterns.
        Returns list of detected issues.
        """
        antipatterns = []
        
        # 1. Repeated failures (same category, multiple failures)
        category_failures: dict[str, list] = {}
        for d in self.decisions:
            if d.get("outcome") == "failure":
                cat = d.get("category", "unknown")
                if cat not in category_failures:
                    category_failures[cat] = []
                category_failures[cat].append(d)
        
        for cat, failures in category_failures.items():
            if len(failures) >= 2:
                antipatterns.append(AntiPattern(
                    pattern_type="repeated_failure",
                    description=f"Multiple failures in '{cat}' category",
                    severity="high" if len(failures) >= 3 else "medium",
                    decisions=failures,
                ))
        
        # 2. Low confidence decisions without review
        low_conf_no_review = [
            d for d in self.decisions
            if d.get("confidence", 1) < 0.5 and not d.get("reviewed", False)
        ]
        if low_conf_no_review:
            antipatterns.append(AntiPattern(
                pattern_type="low_confidence_unreviewed",
                description="Low-confidence decisions made without review",
                severity="medium",
                decisions=low_conf_no_review,
            ))
        
        # 3. Single reason type (fragile reasoning)
        single_reason = []
        for d in self.decisions:
            reasons = d.get("reasons", [])
            if isinstance(reasons, list) and len(reasons) == 1:
                single_reason.append(d)
        
        if len(single_reason) >= 3:
            antipatterns.append(AntiPattern(
                pattern_type="single_reason",
                description="Decisions with only one supporting reason (fragile)",
                severity="low",
                decisions=single_reason,
            ))
        
        # 4. Missing context (no similar query before decision)
        # This would require tracking query history - placeholder for now
        
        return {
            "total_antipatterns": len(antipatterns),
            "antipatterns": [a.to_dict() for a in antipatterns],
        }
    
    def full_report(self) -> dict:
        """Generate complete pattern analysis report."""
        return {
            "calibration": self.calibration_report(),
            "categories": self.category_analysis(),
            "antipatterns": self.detect_antipatterns(),
        }
