# Feature: Pattern Detection Engine

## Overview
Analyze indexed decisions to detect patterns, correlate confidence with outcomes, and surface insights.

## User Stories

### US-1: Confidence Calibration Report
**As an** AI agent reviewing my decisions  
**I want to** see how well my confidence predictions match actual outcomes  
**So that** I can improve my calibration over time

**Acceptance Criteria:**
- [ ] Calculate Brier scores across all decisions with outcomes
- [ ] Group by confidence buckets (0-20%, 20-40%, etc.)
- [ ] Show calibration curve (predicted vs actual success rate)
- [ ] Identify systematic over/under-confidence

### US-2: Category Pattern Analysis
**As an** AI agent  
**I want to** see patterns by decision category  
**So that** I know which areas I decide well vs poorly

**Acceptance Criteria:**
- [ ] Aggregate outcomes by category
- [ ] Calculate success rate per category
- [ ] Identify categories with low confidence or poor outcomes
- [ ] Suggest areas needing more research before deciding

### US-3: Anti-Pattern Detection
**As an** AI agent  
**I want to** be warned about recurring failure patterns  
**So that** I can break bad decision habits

**Acceptance Criteria:**
- [ ] Detect repeated decisions with same negative outcome
- [ ] Identify "flip-flopping" (contradictory decisions)
- [ ] Flag decisions made without consulting similar past cases
- [ ] Surface decisions lacking required context

### US-4: Reason Type Effectiveness
**As an** AI agent  
**I want to** know which reason types lead to better outcomes  
**So that** I can weight my reasoning appropriately

**Acceptance Criteria:**
- [ ] Track outcome by reason type (pattern, analysis, authority, etc.)
- [ ] Identify reason types that correlate with success
- [ ] Flag decisions with only one reason type (fragile)
- [ ] Recommend reason diversity for robustness

## Technical Requirements

### TR-1: Pattern Analysis Pipeline
```python
class PatternDetector:
    def calibration_report(self, decisions: list) -> CalibrationReport
    def category_analysis(self, decisions: list) -> CategoryReport
    def anti_patterns(self, decisions: list) -> list[AntiPattern]
    def reason_effectiveness(self, decisions: list) -> ReasonReport
```

### TR-2: Minimum Data Requirements
- Calibration: ≥10 decisions with outcomes
- Category analysis: ≥5 decisions per category
- Anti-patterns: ≥20 total decisions
- Reason analysis: ≥10 decisions with multi-reason

### TR-3: Output Formats
- CLI: Human-readable tables and summaries
- JSON: Structured data for programmatic use
- Markdown: For inclusion in daily/weekly reports

## API Design

### Calibration Report
```bash
cognition patterns calibration --format table
```

**Output:**
```
Confidence Calibration Report
=============================
Bucket     | Predicted | Actual | Decisions | Brier
0-20%      | 10%       | 15%    | 5         | 0.12
20-40%     | 30%       | 28%    | 8         | 0.08
40-60%     | 50%       | 52%    | 12        | 0.05
60-80%     | 70%       | 65%    | 15        | 0.07
80-100%    | 90%       | 88%    | 10        | 0.04

Overall Brier Score: 0.072 (Good calibration)
```

### Category Analysis
```bash
cognition patterns categories
```

### Anti-Pattern Alerts
```bash
cognition patterns antipatterns
```

## Integration with OpenClaw

### Heartbeat Check
Add to HEARTBEAT.md:
```markdown
## Decision Pattern Review (weekly)
Run `cognition patterns calibration` and review:
- Are any categories consistently low confidence?
- Any anti-patterns emerging?
- Update guardrails based on findings
```

### Proactive Alerts
When patterns cross thresholds:
- Brier score > 0.15: "⚠️ Calibration drifting"
- Category success < 50%: "⚠️ Struggling with {category} decisions"
- Same failure 3x: "🚫 Recurring anti-pattern detected"

## Out of Scope (v0.6.0)
- Automated guardrail generation from patterns
- Cross-agent pattern comparison
- Real-time pattern streaming
