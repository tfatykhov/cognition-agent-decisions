# Guardrails Authoring Guide

This guide explains how to write custom guardrail rules to enforce decision-making policies in your organization.

---

## What Are Guardrails?

Guardrails are YAML-defined rules that are evaluated against a decision context **before** the decision is committed. They can:

- **Block** — Prevent the decision entirely
- **Warn** — Allow but flag the risk
- **Log** — Record for audit without blocking

---

## Guardrail Structure

```yaml
- id: unique-guardrail-id          # Required: unique identifier
  description: Human-readable text  # Required: what this rule does
  
  # Conditions — when does this rule apply?
  condition_<field>: <value>        # Field-based condition matching
  
  # Requirements — what must be true?
  requires_<field>: true            # Boolean requirement check
  
  # Scope — which projects does this apply to?
  scope: ProjectName                # Optional: restrict to specific projects
  
  # Action — what to do on violation
  action: block                     # block | warn | log
  
  # Message — what to tell the agent
  message: "Explanation of the violation"
```

---

## Condition Types

### Field Conditions

Match a specific field in the decision context:

```yaml
# Exact match
condition_category: architecture

# Comparison operators (prefix in string)
condition_confidence: "< 0.5"
condition_confidence: "> 0.8"
condition_confidence: "<= 0.3"
condition_confidence: ">= 0.9"
condition_confidence: "!= 0.5"

# Boolean match
condition_affects_production: true

# String match
condition_stakes: high
condition_decision_type: strategy_change
```

### Operator Reference

| Operator | Syntax | Example |
|----------|--------|---------|
| Equals | `field: value` | `condition_category: trading` |
| Not equals | `field: "!= value"` | `condition_stakes: "!= low"` |
| Less than | `field: "< value"` | `condition_confidence: "< 0.5"` |
| Greater than | `field: "> value"` | `condition_position_size_pct: "> 10"` |
| Less/equal | `field: "<= value"` | `condition_confidence: "<= 0.3"` |
| Greater/equal | `field: ">= value"` | `condition_confidence: ">= 0.9"` |

### V2 Conditions (Advanced)

For more complex scenarios, use the v2 structured condition format:

```yaml
conditions:
  - type: field
    field: stakes
    operator: "=="
    value: high

  - type: semantic
    query_field: description
    threshold: 0.85
    filter_outcome: failure
    filter_since_days: 30
    min_matches: 2

  - type: temporal
    field: category
    value: deployment
    window_hours: 24
    max_occurrences: 2

  - type: aggregate
    field: category
    value: trading
    metric: success_rate
    operator: "<"
    threshold: 0.5

  - type: compound
    operator: and   # or | or
    conditions:
      - type: field
        field: stakes
        operator: "=="
        value: critical
      - type: field
        field: confidence
        operator: "<"
        value: 0.7
```

---

## Requirements

Requirements are boolean checks — the named field must be `true` in the context:

```yaml
# Requires code review to be completed
requires_code_review: true

# Requires backtest to have run
requires_backtest_completed: true

# Requires risk assessment
requires_risk_assessed: true

# Requires human approval
requires_human_approval: true

# Custom requirements
requires_monitoring_configured: true
requires_rollback_plan: true
requires_ci_green: true
requires_audit_logged: true
```

If the corresponding field is missing or `false` in the context, the requirement fails.

---

## Scope

Restrict a guardrail to specific projects:

```yaml
# Single scope
scope: CryptoTrader

# The guardrail only applies when the context has:
# { "scope": "CryptoTrader" } or { "project": "CryptoTrader" }
```

---

## Actions

| Action | Behavior | Return |
|--------|----------|--------|
| `block` | Prevents the decision | `allowed: false` |
| `warn` | Allows but flags concern | `allowed: true` (with warnings) |
| `log` | Silently records evaluation | `allowed: true` |

---

## Examples

### Cornerstone Rules (Non-Negotiable)

```yaml
# guardrails/cornerstone.yaml

- id: no-production-without-review
  description: Production changes require code review
  condition_affects_production: true
  requires_code_review: true
  action: block
  message: Production changes require completed code review

- id: no-high-stakes-low-confidence
  description: High-stakes decisions need minimum confidence
  condition_stakes: high
  condition_confidence: "< 0.5"
  action: block
  message: High-stakes decisions require 50% confidence or more

- id: no-trading-strategy-without-backtest
  description: Trading strategy changes need backtesting
  scope: CryptoTrader
  condition_category: trading
  condition_decision_type: strategy_change
  requires_backtest_completed: true
  action: block
  message: Trading strategy changes require completed backtest
```

### Financial Template

```yaml
# guardrails/templates/financial.yaml

template:
  name: financial
  description: Guardrails for financial and trading decisions
  version: "1.0"

guardrails:
  - id: require-backtest
    description: Strategy changes require backtesting
    condition_category: trading
    condition_decision_type: strategy_change
    requires_backtest_completed: true
    action: block
    message: "Trading strategy changes require completed backtest"

  - id: require-risk-assessment
    description: Financial decisions need risk assessment
    condition_category: financial
    condition_stakes: high
    requires_risk_assessed: true
    action: block
    message: "High-stakes financial decisions require risk assessment"

  - id: limit-single-position
    description: Warn on large position sizes
    condition_category: trading
    condition_position_size_pct: "> 10"
    action: warn
    message: "Position size exceeds 10% of portfolio - review risk"

  - id: require-approval-large-amounts
    description: Large transactions need approval
    condition_amount_usd: "> 10000"
    requires_human_approval: true
    action: block
    message: "Transactions over $10k require human approval"

  - id: no-trading-during-volatility
    description: Pause new trades during high volatility
    condition_category: trading
    condition_market_volatility: high
    action: warn
    message: "High market volatility detected - consider pausing new positions"
```

### Production Safety Template

```yaml
# guardrails/templates/production-safety.yaml

template:
  name: production-safety
  description: Guardrails for production deployments
  version: "1.0"

guardrails:
  - id: require-code-review
    description: All production changes must be code reviewed
    condition_affects_production: true
    requires_code_review: true
    action: block
    message: "Production changes require completed code review"

  - id: require-tests-passing
    description: CI tests must pass before production deploy
    condition_affects_production: true
    requires_ci_green: true
    action: block
    message: "CI tests must pass before deploying to production"

  - id: require-rollback-plan
    description: Production deploys need rollback strategy
    condition_affects_production: true
    condition_change_type: deployment
    requires_rollback_plan: true
    action: warn
    message: "Consider documenting rollback plan before deploying"

  - id: no-friday-deploys
    description: Avoid production deploys on Fridays
    condition_affects_production: true
    condition_day_of_week: friday
    action: warn
    message: "Friday deploys are risky - consider waiting until Monday"
```

---

## Writing Your Own Guardrails

### Step 1: Create a YAML File

```bash
# Create in the guardrails directory
touch guardrails/my-project-rules.yaml
```

### Step 2: Define Rules

Think about:

1. **What decisions should be blocked?** → Use `action: block`
2. **What decisions should be flagged?** → Use `action: warn`
3. **What conditions trigger the rule?** → Use `condition_*` fields
4. **What requirements must be met?** → Use `requires_*` fields

### Step 3: Test Locally

```bash
# List guardrails to verify they load
python bin/cognition guardrails

# Test with a specific context
python bin/cognition check --category trading --stakes high --confidence 0.3
```

### Step 4: Deploy

Place your YAML file in a configured guardrail directory:

```bash
GUARDRAILS_PATHS=/app/guardrails:/app/my-custom-guardrails
```

---

## Audit Trail

Every guardrail evaluation is recorded in the audit trail:

**Output location:** `audit/YYYY-MM-DD-<decision_id>.json`

**Contents:**

```json
{
  "decision_id": "2026-02-07-decision-a1b2c3d4",
  "timestamp": "2026-02-07T12:00:00Z",
  "overall_allowed": false,
  "evaluations": [
    {
      "guardrail_id": "no-production-without-review",
      "matched": true,
      "passed": false,
      "action": "block",
      "message": "Production changes require completed code review"
    }
  ],
  "override": null
}
```

### Querying Audit Records

The `AuditLog` class provides methods for querying:

- `get_violations(since)` — All violations since a timestamp
- `get_statistics()` — Aggregate stats: total evaluations, block rate, most triggered rules
- `get_overrides()` — Decisions where violations were overridden

---

## Best Practices

1. **Start with cornerstone rules** — Block non-negotiable violations (safety, compliance)
2. **Use warnings for soft guidelines** — Don't block everything; let agents learn
3. **Scope to projects** — Use `scope:` to avoid overly broad rules
4. **Write clear messages** — Agents need to understand *why* they were blocked
5. **Review audit trails** — Monitor which rules trigger most often
6. **Version your templates** — Include `version:` for tracking changes
7. **Test before deploying** — Use the CLI to verify rules work as expected
