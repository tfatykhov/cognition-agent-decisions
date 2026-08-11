"""
Framework mapping rule engine for F055 Decision Provenance.

Loads declarative YAML rule files and applies them to event streams.
Coverage is computed and reported SEPARATELY per evidence class — never blended.

  observed_coverage_pct — % of observed events with at least one framework mapping
  attested_coverage_pct — % of attested events with at least one framework mapping

A control satisfied only by attested evidence is flagged attested_only=True and
must be rendered distinctly in any bundle output (including PDF).

Evidence class isolation: each YAML file declares its evidence_class at the top
level. Rules from that file only match events of the same class — observed rules
never match attested events and vice versa (finding 7).
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

MAPPINGS_DIR = Path(__file__).parent / "mappings"
INSUFFICIENT_EVIDENCE_TAG = "INSUFFICIENT_EVIDENCE"


@dataclass
class EvidenceClassStats:
    """Coverage stats for a single evidence class."""

    total_events: int = 0
    mapped_events: int = 0
    unmapped_events: int = 0
    coverage_pct: float = 0.0


@dataclass
class MappingResult:
    """Result of applying framework rules to an event stream.

    Coverage is reported separately per class. There is no blended coverage_pct
    anywhere in this structure — that is intentional and load-bearing.
    """

    observed: EvidenceClassStats = field(default_factory=EvidenceClassStats)
    attested: EvidenceClassStats = field(default_factory=EvidenceClassStats)
    mappings: list[dict] = field(default_factory=list)
    insufficient_evidence: list[dict] = field(default_factory=list)
    unmapped: list[dict] = field(default_factory=list)
    attested_only_controls: set[str] = field(default_factory=set)

    @property
    def total_insufficient_evidence(self) -> int:
        return len(self.insufficient_evidence)


def load_rules(mappings_dir: Path = MAPPINGS_DIR) -> list[dict]:
    """Load all YAML rule files from mappings_dir. Returns combined list of rules.

    Each rule carries '_evidence_class' from the file header so that
    _rule_matches can enforce class isolation (finding 7).
    """
    all_rules = []
    for yaml_file in sorted(mappings_dir.glob("*.yaml")):
        # encoding is explicit: the rule files carry non-ASCII control text that
        # reaches auditor-facing bundles, and the platform default (cp1252 on
        # Windows) mis-decodes it silently rather than raising.
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        framework = data.get("framework", yaml_file.stem)
        file_evidence_class = data.get("evidence_class", "observed")
        for rule in data.get("rules", []):
            rule = dict(rule)
            rule["_framework"] = framework
            rule["_file"] = yaml_file.name
            rule["_evidence_class"] = file_evidence_class
            all_rules.append(rule)
    return all_rules


def _check_condition(payload: dict, condition: dict) -> bool:
    """Evaluate a single condition against an event payload."""
    field_name = condition.get("field")
    value = payload.get(field_name)

    if "equals" in condition:
        return value == condition["equals"]
    if "gt" in condition:
        return value is not None and value > condition["gt"]
    if "lt" in condition:
        return value is not None and value < condition["lt"]
    if "truthy" in condition:
        return bool(value) == condition["truthy"]
    if "in" in condition:
        return value in condition["in"]
    return value is not None


def _rule_matches(event: dict, rule: dict) -> bool:
    """Return True if a rule's match block applies to this event.

    Evidence class isolation (finding 7): a rule from an 'observed' file only
    matches observed events; a rule from an 'attested' file only matches attested
    events. This prevents high-trust observed credit from being awarded to
    self-reported attested events and vice versa.
    """
    # Class isolation: reject cross-class matches
    rule_class = rule.get("_evidence_class", "observed")
    event_class = event.get("evidence_class", "observed")
    if rule_class != event_class:
        return False

    match = rule.get("match", {})
    if match.get("event_type") != event.get("event_type"):
        return False
    for condition in match.get("conditions", []):
        if not _check_condition(event.get("payload", {}), condition):
            return False
    return True


def apply_rules(events: list[dict], rules: list[dict]) -> MappingResult:
    """Apply all rules to all events, computing per-class coverage.

    An event is 'mapped' if at least one rule matched it (including INSUFFICIENT_EVIDENCE).
    An event is 'unmapped' if no rule matched it at all.

    Coverage is computed separately for 'observed' and 'attested' events.
    There is NO single blended coverage_pct.
    """
    result = MappingResult()

    # Track which seqs were mapped, keyed by evidence_class
    mapped_seqs_by_class: dict[str, set] = {"observed": set(), "attested": set()}

    for event in events:
        seq = event.get("seq")
        event_type = event.get("event_type")
        ev_class = event.get("evidence_class", "observed")

        for rule in rules:
            if not _rule_matches(event, rule):
                continue

            mapped_seqs_by_class.setdefault(ev_class, set()).add(seq)

            entry: dict = {
                "seq": seq,
                "event_type": event_type,
                "pr_number": event.get("payload", {}).get("pr_number"),
                "rule_id": rule.get("id"),
                "framework": rule.get("_framework"),
                "stage": rule.get("stage"),
                "function_id": rule.get("function_id"),
                "control_name": rule.get("control_name"),
                "ts": event.get("ts"),
                "evidence_class": ev_class,
            }
            if rule.get("stretch"):
                entry["stretch"] = True
            if rule.get("confidence"):
                entry["confidence"] = rule.get("confidence")

            if rule.get("insufficient_evidence"):
                entry["type"] = INSUFFICIENT_EVIDENCE_TAG
                entry["reason"] = rule.get("reason", "").strip()
                result.insufficient_evidence.append(entry)
            else:
                entry["type"] = "mapping"
                entry["description"] = rule.get("description", "").strip()
                result.mappings.append(entry)

    # Identify unmapped events
    for event in events:
        seq = event.get("seq")
        ev_class = event.get("evidence_class", "observed")
        if seq not in mapped_seqs_by_class.get(ev_class, set()):
            result.unmapped.append({
                "seq": seq,
                "event_type": event.get("event_type"),
                "pr_number": event.get("payload", {}).get("pr_number"),
                "ts": event.get("ts"),
                "evidence_class": ev_class,
            })

    # Compute per-class coverage
    obs_total = sum(1 for e in events if e.get("evidence_class", "observed") == "observed")
    att_total = sum(1 for e in events if e.get("evidence_class") == "attested")

    result.observed.total_events = obs_total
    result.observed.mapped_events = len(mapped_seqs_by_class.get("observed", set()))
    result.observed.unmapped_events = obs_total - result.observed.mapped_events
    if obs_total > 0:
        result.observed.coverage_pct = round(
            result.observed.mapped_events / obs_total * 100, 1
        )

    result.attested.total_events = att_total
    result.attested.mapped_events = len(mapped_seqs_by_class.get("attested", set()))
    result.attested.unmapped_events = att_total - result.attested.mapped_events
    if att_total > 0:
        result.attested.coverage_pct = round(
            result.attested.mapped_events / att_total * 100, 1
        )

    # Identify attested-only controls: controls with attested mappings but NO observed mappings
    observed_control_ids: set[str] = {
        m["function_id"] for m in result.mappings if m.get("evidence_class") == "observed"
    }
    attested_control_ids: set[str] = {
        m["function_id"] for m in result.mappings if m.get("evidence_class") == "attested"
    }
    result.attested_only_controls = attested_control_ids - observed_control_ids

    # Tag attested-only mappings in the list
    for m in result.mappings:
        if m.get("function_id") in result.attested_only_controls:
            m["attested_only"] = True

    return result
