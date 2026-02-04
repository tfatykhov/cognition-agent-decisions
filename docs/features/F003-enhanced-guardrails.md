# Feature: Enhanced Guardrails

## Overview
Expand guardrail system with more conditions, dynamic policies, and integration with decision outcomes.

## User Stories

### US-1: Outcome-Based Guardrails
**As an** AI agent  
**I want to** guardrails that learn from past outcomes  
**So that** policies adapt based on what actually works

**Acceptance Criteria:**
- [ ] Guardrails can reference historical success rates
- [ ] "Block if similar decisions failed >50% of time"
- [ ] Dynamic thresholds based on category performance
- [ ] Manual override with justification logged

### US-2: Context-Aware Conditions
**As an** AI agent  
**I want to** guardrails that consider rich context  
**So that** policies aren't just simple field checks

**Acceptance Criteria:**
- [ ] Semantic similarity conditions ("if similar to failed decision X")
- [ ] Time-based conditions ("if decided same thing within 24h")
- [ ] Dependency conditions ("if blocks decision Y")
- [ ] Compound AND/OR logic

### US-3: Guardrail Audit Trail
**As a** human reviewer  
**I want to** see which guardrails fired on each decision  
**So that** I can audit agent behavior

**Acceptance Criteria:**
- [ ] Each decision logs guardrails evaluated
- [ ] Record: guardrail ID, result, action taken
- [ ] Query decisions by guardrail violations
- [ ] Export audit report

### US-4: Guardrail Templates
**As an** AI agent setting up guardrails  
**I want to** use pre-built templates  
**So that** I don't start from scratch

**Acceptance Criteria:**
- [ ] Template: production-safety (review, testing, rollback)
- [ ] Template: financial (limits, approvals, audit)
- [ ] Template: communication (tone, recipients, timing)
- [ ] Customizable parameters per template

## Guardrail Definition Language v2

### Current (v1)
```yaml
- id: no-high-stakes-low-confidence
  condition_stakes: high
  condition_confidence: "< 0.5"
  action: block
```

### Enhanced (v2)
```yaml
- id: no-repeat-failures
  description: Block if similar decisions failed recently
  conditions:
    - type: semantic_similarity
      query: "{{decision}}"
      threshold: 0.8
      filter:
        outcome: failure
        since: 7d
      min_matches: 2
  action: block
  message: "Similar decisions failed {{match_count}} times recently"
  
- id: require-diverse-reasoning
  description: Warn if only one reason type
  conditions:
    - type: field
      field: reason_types_count
      operator: lt
      value: 2
  action: warn
  message: "Consider adding diverse reasoning (current: {{reason_types}})"
```

### Condition Types
| Type | Description | Example |
|------|-------------|---------|
| `field` | Simple field comparison | `confidence < 0.5` |
| `semantic_similarity` | Vector similarity check | "similar to failed decisions" |
| `temporal` | Time-based checks | "within 24h of similar" |
| `aggregate` | Statistical checks | "category success < 50%" |
| `dependency` | Decision relationships | "blocks another decision" |

## Technical Requirements

### TR-1: Condition Evaluators
```python
class ConditionEvaluator(Protocol):
    def evaluate(self, condition: dict, context: dict) -> bool: ...

class SemanticSimilarityEvaluator(ConditionEvaluator):
    def __init__(self, index: SemanticIndex): ...
    
class TemporalEvaluator(ConditionEvaluator):
    def __init__(self, decision_store: DecisionStore): ...
```

### TR-2: Audit Schema
```yaml
decision_id: "2026-02-04-architecture-choice"
guardrails_evaluated:
  - id: no-high-stakes-low-confidence
    matched: false
    action: skip
  - id: no-production-without-review
    matched: true
    passed: true
    action: pass
  - id: no-repeat-failures
    matched: true
    passed: false
    action: warn
    message: "Similar decision failed 2 times"
    override: true
    override_reason: "Different context - new requirements"
```

### TR-3: Template System
```
guardrails/
├── templates/
│   ├── production-safety.yaml
│   ├── financial.yaml
│   └── communication.yaml
├── cornerstone.yaml
└── custom.yaml
```

## API Design

### Apply Template
```bash
cognition guardrails apply-template production-safety \
  --review-required true \
  --testing-required true
```

### Audit Query
```bash
cognition guardrails audit --since 7d --violations-only
```

### Override with Reason
```bash
cognition check --override --reason "Approved by Tim for urgent fix"
```

## Out of Scope (v0.6.0)
- Guardrail learning from outcomes (v0.8.0)
- Cross-agent guardrail inheritance
- Real-time guardrail updates
