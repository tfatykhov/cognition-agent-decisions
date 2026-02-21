# F052: Pre-Built Decision Quality Dashboard

**Status:** Proposed
**Priority:** P2
**Category:** Observability
**Related:** F049 (Dashboard), F051 (Docker Demo)

## Problem

The current dashboard is tightly coupled to the CSTP server deployment. Users who want decision intelligence observability in their existing monitoring stack (Grafana, Datadog, custom dashboards) can't easily extract and visualize calibration data. The dashboard is also not embeddable or exportable.

Competing tools (AgentOps, Helicone) ship Grafana dashboard JSONs and embeddable widgets. "Observability for agent intelligence" needs to be tangible and demo-able outside our own UI.

## Solution

Ship pre-built, exportable dashboard configurations and a metrics API that integrates with standard observability tooling.

### What Ships

```
dashboards/
  grafana/
    cognition-engines.json       # Grafana dashboard JSON (import-ready)
    provisioning.yml             # Auto-provisioning config
  standalone/
    calibration-widget.html      # Self-contained HTML widget
    embed.js                     # Embeddable JS snippet
  screenshots/                   # For README/docs
```

### Metrics API Endpoint

New endpoint: `cstp.getMetrics` (JSON-RPC) and `/metrics` (Prometheus format)

```json
// cstp.getMetrics response
{
  "decisions": {
    "total": 333,
    "reviewed": 158,
    "by_category": {"architecture": 45, "process": 120, ...},
    "by_outcome": {"success": 145, "partial": 8, "failure": 5}
  },
  "calibration": {
    "brier_score": 0.019,
    "accuracy": 0.975,
    "gap": 0.084,
    "buckets": [
      {"range": "0.5-0.6", "count": 1, "success_rate": 1.0, "expected": 0.55},
      {"range": "0.9-1.0", "count": 110, "success_rate": 0.99, "expected": 0.95}
    ]
  },
  "activity": {
    "decisions_24h": 6,
    "reviews_24h": 6,
    "avg_quality_score": 0.72,
    "guardrail_blocks_24h": 0
  },
  "agents": {
    "active": ["emerson", "code-reviewer", "docs-agent"],
    "decisions_by_agent": {"emerson": 300, "code-reviewer": 25, "docs-agent": 8}
  }
}
```

### Prometheus Metrics

```
# HELP cstp_decisions_total Total number of decisions recorded
# TYPE cstp_decisions_total counter
cstp_decisions_total{category="architecture"} 45
cstp_decisions_total{category="process"} 120

# HELP cstp_calibration_brier Brier score (lower is better)
# TYPE cstp_calibration_brier gauge
cstp_calibration_brier 0.019

# HELP cstp_calibration_accuracy Overall accuracy rate
# TYPE cstp_calibration_accuracy gauge
cstp_calibration_accuracy 0.975

# HELP cstp_guardrail_blocks_total Total guardrail blocks
# TYPE cstp_guardrail_blocks_total counter
cstp_guardrail_blocks_total{guardrail="low-quality-recording"} 12

# HELP cstp_decision_quality Average quality score
# TYPE cstp_decision_quality gauge
cstp_decision_quality 0.72
```

### Grafana Dashboard Panels

The pre-built Grafana dashboard includes:

1. **Calibration Curve** - Expected vs actual success rate by confidence bucket (scatter + line)
2. **Brier Score Trend** - Rolling 30-day Brier score (line chart)
3. **Decision Volume** - Decisions per day, colored by category (stacked bar)
4. **Outcome Distribution** - Success/partial/failure/abandoned (pie chart)
5. **Confidence Distribution** - Histogram of confidence values
6. **Quality Score Trend** - Average quality score over time
7. **Agent Activity** - Decisions by agent (table)
8. **Guardrail Blocks** - Blocks per day with guardrail breakdown
9. **Review Backlog** - Unreviewed decisions count + age
10. **Category Performance** - Success rate by category (bar chart)

### Standalone HTML Widget

A self-contained HTML file that fetches from the metrics API and renders:
- Calibration curve (Chart.js)
- Key stats (Brier, accuracy, total decisions)
- Embeddable via iframe or `<script>` tag

## Implementation

### Phase 1: Metrics API (P1)
- Add `cstp.getMetrics` JSON-RPC method
- Add `/metrics` HTTP endpoint (Prometheus text format)
- Reuse existing `getCalibration` and `getStats` internals

### Phase 2: Grafana Dashboard JSON (P1)
- Create Grafana dashboard JSON using Prometheus datasource
- Test with docker-compose Grafana + Prometheus setup
- Add to `demo/` docker-compose as optional service

### Phase 3: Standalone Widget (P2)
- Single HTML file with inline CSS/JS
- Fetches from configurable CSTP endpoint
- Auto-refresh every 60s
- Dark/light theme support

### Phase 4: Documentation (P2)
- Screenshots for README and website
- Integration guides for Grafana, Datadog, custom
- "Add to your monitoring stack in 5 minutes" guide

## Success Criteria

- Grafana dashboard importable in < 2 minutes
- Prometheus metrics scrapeable with standard config
- Standalone widget works with zero build step
- All 10 Grafana panels render correctly with demo seed data
- Widget loads in < 1 second

## Risks

- **Prometheus dependency** - Not all users have Prometheus. Mitigate: JSON API works standalone.
- **Grafana version compatibility** - Dashboard JSON may break across versions. Mitigate: test with Grafana 10+.
- **Metric cardinality** - Too many labels could cause issues. Mitigate: keep label set small and fixed.
