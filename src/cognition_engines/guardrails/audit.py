"""
Audit Trail for Guardrail Evaluations
Logs which guardrails were evaluated for each decision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class GuardrailEvaluation:
    """Record of a single guardrail evaluation."""
    guardrail_id: str
    matched: bool
    passed: bool
    action: str  # pass, skip, warn, block
    message: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.guardrail_id,
            "matched": self.matched,
            "passed": self.passed,
            "action": self.action,
            "message": self.message,
        }


@dataclass
class AuditRecord:
    """Complete audit record for a decision."""
    decision_id: str
    timestamp: str
    context: dict
    evaluations: list[GuardrailEvaluation] = field(default_factory=list)
    overall_allowed: bool = True
    override: bool = False
    override_reason: str = ""
    
    def add_evaluation(self, eval: GuardrailEvaluation):
        self.evaluations.append(eval)
        if not eval.passed and eval.action == "block":
            self.overall_allowed = False
    
    def set_override(self, reason: str):
        """Override a blocked decision with justification."""
        self.override = True
        self.override_reason = reason
        self.overall_allowed = True
    
    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "context": self.context,
            "overall_allowed": self.overall_allowed,
            "override": self.override,
            "override_reason": self.override_reason if self.override else None,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "summary": {
                "total": len(self.evaluations),
                "passed": sum(1 for e in self.evaluations if e.passed),
                "warnings": sum(1 for e in self.evaluations if not e.passed and e.action == "warn"),
                "blocks": sum(1 for e in self.evaluations if not e.passed and e.action == "block"),
            }
        }
    
    def to_yaml_block(self) -> str:
        """Generate YAML block for embedding in decision file."""
        lines = [
            "guardrail_audit:",
            f"  timestamp: \"{self.timestamp}\"",
            f"  allowed: {str(self.overall_allowed).lower()}",
        ]
        
        if self.override:
            lines.append("  override: true")
            lines.append(f"  override_reason: \"{self.override_reason}\"")
        
        lines.append("  evaluations:")
        for e in self.evaluations:
            lines.append(f"    - id: {e.guardrail_id}")
            lines.append(f"      matched: {str(e.matched).lower()}")
            lines.append(f"      passed: {str(e.passed).lower()}")
            lines.append(f"      action: {e.action}")
            if e.message:
                lines.append(f"      message: \"{e.message}\"")
        
        return "\n".join(lines)


class AuditLog:
    """Manages audit records for guardrail evaluations."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path.cwd() / "audit"
        self.records: list[AuditRecord] = []
    
    def create_record(self, decision_id: str, context: dict) -> AuditRecord:
        """Create a new audit record."""
        record = AuditRecord(
            decision_id=decision_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            context=context,
        )
        self.records.append(record)
        return record
    
    def save_record(self, record: AuditRecord):
        """Save audit record to file."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Use date-based filename
        date_str = record.timestamp[:10]
        filename = f"{date_str}-{record.decision_id}.json"
        
        path = self.log_dir / filename
        with open(path, "w") as f:
            json.dump(record.to_dict(), f, indent=2)
    
    def query_violations(
        self,
        since_days: int = 7,
        action_filter: str = None,
    ) -> list[dict]:
        """Query audit records for violations."""
        violations = []
        
        if not self.log_dir.exists():
            return violations
        
        # Calculate cutoff date for filtering
        from datetime import datetime, timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%d")
        
        for path in self.log_dir.glob("*.json"):
            # Filter by filename date (format: YYYY-MM-DD-*.json)
            filename = path.name
            file_date = filename[:10] if len(filename) >= 10 else ""
            
            if file_date < cutoff_date:
                continue  # Skip files older than cutoff
            
            try:
                with open(path) as f:
                    record = json.load(f)
                
                for eval in record.get("evaluations", []):
                    if not eval.get("passed", True):
                        if action_filter and eval.get("action") != action_filter:
                            continue
                        
                        violations.append({
                            "decision_id": record.get("decision_id"),
                            "timestamp": record.get("timestamp"),
                            "guardrail": eval.get("id"),
                            "action": eval.get("action"),
                            "message": eval.get("message"),
                            "overridden": record.get("override", False),
                        })
            except Exception:
                pass
        
        return violations
    
    def get_stats(self) -> dict:
        """Get aggregate audit statistics."""
        total_decisions = 0
        total_evaluations = 0
        total_blocks = 0
        total_warnings = 0
        total_overrides = 0
        
        if not self.log_dir.exists():
            return {"error": "No audit log directory"}
        
        for path in self.log_dir.glob("*.json"):
            try:
                with open(path) as f:
                    record = json.load(f)
                
                total_decisions += 1
                summary = record.get("summary", {})
                total_evaluations += summary.get("total", 0)
                total_blocks += summary.get("blocks", 0)
                total_warnings += summary.get("warnings", 0)
                
                if record.get("override"):
                    total_overrides += 1
            except Exception:
                pass
        
        return {
            "total_decisions": total_decisions,
            "total_evaluations": total_evaluations,
            "total_blocks": total_blocks,
            "total_warnings": total_warnings,
            "total_overrides": total_overrides,
            "block_rate": round(total_blocks / max(total_evaluations, 1), 3),
        }
