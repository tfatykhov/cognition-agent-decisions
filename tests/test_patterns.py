"""Tests for pattern detection engine."""

from cognition_engines.patterns.detector import (
    PatternDetector,
    CalibrationBucket,
    CategoryStats,
    AntiPattern,
)


class TestCalibrationBucket:
    """Test calibration bucket calculations."""
    
    def test_empty_bucket(self):
        bucket = CalibrationBucket(0.0, 0.2)
        assert bucket.count == 0
        assert bucket.predicted_rate == 0.0
        assert bucket.actual_rate == 0.0
        assert bucket.brier_score == 0.0
    
    def test_bucket_with_decisions(self):
        bucket = CalibrationBucket(0.6, 0.8)
        bucket.decisions = [
            {"confidence": 0.7, "outcome": "success"},
            {"confidence": 0.75, "outcome": "success"},
            {"confidence": 0.65, "outcome": "failure"},
        ]
        
        assert bucket.count == 3
        assert abs(bucket.predicted_rate - 0.7) < 0.01
        assert abs(bucket.actual_rate - 0.667) < 0.01
    
    def test_bucket_without_outcomes(self):
        bucket = CalibrationBucket(0.4, 0.6)
        bucket.decisions = [
            {"confidence": 0.5},
            {"confidence": 0.55},
        ]
        
        assert bucket.count == 2
        assert bucket.actual_rate == 0.0  # No outcomes
    
    def test_brier_score_perfect(self):
        bucket = CalibrationBucket(0.8, 1.0)
        bucket.decisions = [
            {"confidence": 1.0, "outcome": "success"},
            {"confidence": 0.9, "outcome": "success"},
        ]
        
        # Perfect predictions should have low Brier
        assert bucket.brier_score < 0.1


class TestCategoryStats:
    """Test category statistics."""
    
    def test_empty_category(self):
        stats = CategoryStats("test")
        assert stats.count == 0
        assert stats.avg_confidence == 0.0
        assert stats.success_rate == 0.0
    
    def test_category_with_decisions(self):
        stats = CategoryStats("architecture")
        stats.decisions = [
            {"confidence": 0.8, "outcome": "success"},
            {"confidence": 0.7, "outcome": "success"},
            {"confidence": 0.6, "outcome": "failure"},
        ]
        
        assert stats.count == 3
        assert abs(stats.avg_confidence - 0.7) < 0.01
        assert abs(stats.success_rate - 0.667) < 0.01
    
    def test_to_dict(self):
        stats = CategoryStats("test")
        stats.decisions = [{"confidence": 0.5, "outcome": "success"}]
        
        d = stats.to_dict()
        assert d["category"] == "test"
        assert d["count"] == 1


class TestAntiPattern:
    """Test anti-pattern representation."""
    
    def test_to_dict(self):
        ap = AntiPattern(
            pattern_type="repeated_failure",
            description="Test pattern",
            severity="high",
            decisions=[{"title": "Decision 1"}, {"title": "Decision 2"}],
        )
        
        d = ap.to_dict()
        assert d["type"] == "repeated_failure"
        assert d["severity"] == "high"
        assert d["decision_count"] == 2


class TestPatternDetector:
    """Test pattern detector."""
    
    def test_init_empty(self):
        detector = PatternDetector()
        assert len(detector.decisions) == 0
    
    def test_init_with_decisions(self):
        decisions = [{"title": "Test"}]
        detector = PatternDetector(decisions)
        assert len(detector.decisions) == 1
    
    def test_parse_yaml_basic(self):
        """Test basic YAML parsing."""
        detector = PatternDetector()
        content = """
title: Test Decision
confidence: 0.8
outcome: success
category: architecture
"""
        result = detector._parse_yaml(content)
        assert result["title"] == "Test Decision"
        assert result["confidence"] == 0.8
        assert result["outcome"] == "success"
    
    def test_parse_yaml_with_list(self):
        """Test YAML parsing with list items."""
        detector = PatternDetector()
        content = """
title: Test
reasons:
  - type: pattern
    description: First reason
  - type: analysis
    description: Second reason
"""
        result = detector._parse_yaml(content)
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1
    
    def test_parse_yaml_multiline(self):
        """Test YAML parsing with multiline string."""
        detector = PatternDetector()
        content = """
title: Test
context: |
  This is a multiline
  context string
decision: Made it
"""
        result = detector._parse_yaml(content)
        assert "context" in result
        assert "multiline" in result["context"]
    
    def test_calibration_report_empty(self):
        detector = PatternDetector([])
        report = detector.calibration_report()
        
        assert report["total_decisions"] == 0
        assert report["overall_brier"] == 0.0
    
    def test_calibration_report_with_decisions(self):
        decisions = [
            {"confidence": 0.9, "outcome": "success"},
            {"confidence": 0.8, "outcome": "success"},
            {"confidence": 0.3, "outcome": "failure"},
        ]
        detector = PatternDetector(decisions)
        report = detector.calibration_report()
        
        assert report["total_decisions"] == 3
        assert report["with_outcomes"] == 3
        assert report["overall_brier"] < 0.2  # Should be well calibrated
    
    def test_calibration_handles_percentage_confidence(self):
        """Confidence stored as 80 instead of 0.8."""
        decisions = [
            {"confidence": 80, "outcome": "success"},
            {"confidence": 90, "outcome": "success"},
        ]
        detector = PatternDetector(decisions)
        report = detector.calibration_report()
        
        # Should normalize and not crash
        assert report["total_decisions"] == 2
    
    def test_category_analysis(self):
        decisions = [
            {"category": "architecture", "confidence": 0.8, "outcome": "success"},
            {"category": "architecture", "confidence": 0.7, "outcome": "success"},
            {"category": "process", "confidence": 0.5, "outcome": "failure"},
        ]
        detector = PatternDetector(decisions)
        report = detector.category_analysis()
        
        assert report["total_categories"] == 2
        assert len(report["categories"]) == 2
    
    def test_category_identifies_concerning(self):
        decisions = [
            {"category": "risky", "confidence": 0.3, "outcome": "failure"},
            {"category": "risky", "confidence": 0.4, "outcome": "failure"},
            {"category": "risky", "confidence": 0.35, "outcome": "failure"},
        ]
        detector = PatternDetector(decisions)
        report = detector.category_analysis()
        
        assert len(report["concerning"]) > 0
    
    def test_detect_antipatterns_repeated_failure(self):
        decisions = [
            {"category": "testing", "outcome": "failure"},
            {"category": "testing", "outcome": "failure"},
        ]
        detector = PatternDetector(decisions)
        report = detector.detect_antipatterns()
        
        assert report["total_antipatterns"] >= 1
        types = [ap["type"] for ap in report["antipatterns"]]
        assert "repeated_failure" in types
    
    def test_detect_antipatterns_low_confidence_unreviewed(self):
        decisions = [
            {"confidence": 0.3, "reviewed": False},
            {"confidence": 0.4, "reviewed": False},
        ]
        detector = PatternDetector(decisions)
        report = detector.detect_antipatterns()
        
        types = [ap["type"] for ap in report["antipatterns"]]
        assert "low_confidence_unreviewed" in types
    
    def test_full_report(self):
        decisions = [
            {"category": "arch", "confidence": 0.8, "outcome": "success"},
        ]
        detector = PatternDetector(decisions)
        report = detector.full_report()
        
        assert "calibration" in report
        assert "categories" in report
        assert "antipatterns" in report
