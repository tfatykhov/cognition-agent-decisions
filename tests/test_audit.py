"""Tests for audit trail."""

from cognition_engines.guardrails.audit import (
    GuardrailEvaluation,
    AuditRecord,
    AuditLog,
)


class TestGuardrailEvaluation:
    """Test guardrail evaluation records."""
    
    def test_to_dict(self):
        eval = GuardrailEvaluation(
            guardrail_id="test-rule",
            matched=True,
            passed=False,
            action="block",
            message="Blocked for testing",
        )
        d = eval.to_dict()
        
        assert d["id"] == "test-rule"
        assert d["matched"] is True
        assert d["passed"] is False
        assert d["action"] == "block"
        assert d["message"] == "Blocked for testing"


class TestAuditRecord:
    """Test audit records."""
    
    def test_create_record(self):
        record = AuditRecord(
            decision_id="test-decision",
            timestamp="2026-02-04T02:00:00Z",
            context={"category": "arch"},
        )
        
        assert record.decision_id == "test-decision"
        assert record.overall_allowed is True
        assert len(record.evaluations) == 0
    
    def test_add_passing_evaluation(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="rule-1",
            matched=True,
            passed=True,
            action="pass",
        ))
        
        assert len(record.evaluations) == 1
        assert record.overall_allowed is True
    
    def test_add_blocking_evaluation(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="blocker",
            matched=True,
            passed=False,
            action="block",
        ))
        
        assert record.overall_allowed is False
    
    def test_add_warning_evaluation(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="warner",
            matched=True,
            passed=False,
            action="warn",
        ))
        
        # Warnings don't block
        assert record.overall_allowed is True
    
    def test_override(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="blocker",
            matched=True,
            passed=False,
            action="block",
        ))
        
        assert record.overall_allowed is False
        
        record.set_override("Approved by Tim for urgent fix")
        
        assert record.overall_allowed is True
        assert record.override is True
        assert "Tim" in record.override_reason
    
    def test_to_dict(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={"stakes": "high"},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="rule-1",
            matched=True,
            passed=True,
            action="pass",
        ))
        
        d = record.to_dict()
        
        assert d["decision_id"] == "test"
        assert d["context"]["stakes"] == "high"
        assert d["summary"]["total"] == 1
        assert d["summary"]["passed"] == 1
    
    def test_to_yaml_block(self):
        record = AuditRecord(
            decision_id="test",
            timestamp="2026-02-04T02:00:00Z",
            context={},
        )
        
        record.add_evaluation(GuardrailEvaluation(
            guardrail_id="rule-1",
            matched=True,
            passed=True,
            action="pass",
        ))
        
        yaml_block = record.to_yaml_block()
        
        assert "guardrail_audit:" in yaml_block
        assert "rule-1" in yaml_block
        assert "allowed: true" in yaml_block


class TestAuditLog:
    """Test audit log management."""
    
    def test_create_record(self):
        log = AuditLog()
        record = log.create_record("decision-123", {"category": "arch"})
        
        assert record.decision_id == "decision-123"
        assert len(log.records) == 1
    
    def test_stats_empty(self, tmp_path):
        log = AuditLog(log_dir=tmp_path / "audit")
        stats = log.get_stats()
        
        assert "error" in stats or stats.get("total_decisions", 0) == 0
