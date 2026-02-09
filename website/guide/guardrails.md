# Guardrails

Guardrails are policy rules that prevent agents from making decisions that violate established constraints. They act as **suppressors** - blocking actions at the moment they'd execute.

## Built-in Rules

### no-high-stakes-low-confidence
Blocks high-stakes decisions when confidence is below 50%.

```yaml
- id: no-high-stakes-low-confidence
  condition_stakes: high
  condition_confidence: "< 0.5"
  action: block
  message: High-stakes decisions require 50% confidence or more
```

### no-production-without-review
Blocks production changes that haven't been code reviewed.

```yaml
- id: no-production-without-review
  condition_affects_production: true
  requires_code_review: true
  action: block
  message: Production changes require completed code review
```

## Checking Guardrails

```bash
cstp.py check -d "deploy to production without review" -s high -f 0.85
```

Response when blocked:
```json
{
  "allowed": false,
  "violations": [
    {
      "guardrail_id": "no-production-without-review",
      "message": "Production changes require completed code review"
    }
  ]
}
```

## Custom Guardrails

Add custom rules in `guardrails/` YAML files:

```yaml
- id: no-trading-without-backtest
  description: Trading strategy changes need backtesting
  scope: CryptoTrader
  condition_affects_trading: true
  requires_backtest: true
  action: block
  message: Run backtest before changing trading strategy
```

## Templates

Pre-built guardrail templates are available in `guardrails/templates/`:
- `financial.yaml` - Rules for financial/trading systems
- `production-safety.yaml` - Rules for production deployments

## Future: Censors (F027)

Current guardrails are reactive (block at action time). A future **censor layer** will proactively warn when query results surface failed decisions with similar patterns - intercepting *before* the bad decision forms. See [F027 spec](/specs/f027-censor-layer).
