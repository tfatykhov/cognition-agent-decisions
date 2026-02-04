# F002: Pattern Detection Engine - Implementation Checklist

## Branch: `feature/f002-pattern-detection`

---

## Day 4: Calibration Report

### 4.1 PatternDetector Class
- [ ] Create `src/cognition_engines/patterns/detector.py`
- [ ] `PatternDetector` class with decision loading
- [ ] Unit tests for detector initialization

### 4.2 Brier Score Calculation
- [ ] Implement `calculate_brier_score(decisions)` 
- [ ] Handle decisions with/without outcomes
- [ ] Return overall Brier + per-decision scores
- [ ] Unit tests for Brier calculation

### 4.3 Confidence Bucket Analysis
- [ ] Group decisions by confidence buckets (0-20%, 20-40%, etc.)
- [ ] Calculate predicted vs actual success rate per bucket
- [ ] Identify over/under-confidence patterns
- [ ] Unit tests for bucket analysis

### 4.4 Calibration Report CLI
- [ ] Add `cognition patterns calibration` command
- [ ] JSON output format
- [ ] Text table output format
- [ ] Integration test

---

## Day 5: Category Analysis

### 5.1 Category Aggregation
- [ ] Implement `category_analysis(decisions)`
- [ ] Group by category
- [ ] Calculate: count, avg confidence, success rate
- [ ] Unit tests

### 5.2 Low-Performing Categories
- [ ] Identify categories with <50% success
- [ ] Identify categories with low avg confidence
- [ ] Flag categories needing more research

### 5.3 Category Report CLI
- [ ] Add `cognition patterns categories` command
- [ ] JSON and text output
- [ ] Integration test

---

## Day 6: Anti-Pattern Detection

### 6.1 Repeated Failures
- [ ] Detect same decision made multiple times with failure
- [ ] Threshold: 2+ failures on similar decisions
- [ ] Use semantic similarity for "similar"

### 6.2 Flip-Flop Detection
- [ ] Detect contradictory decisions within time window
- [ ] "Chose A" followed by "Chose not-A"
- [ ] Flag for review

### 6.3 Missing Context Decisions
- [ ] Identify decisions without querying similar first
- [ ] Flag decisions with single reason type

### 6.4 Anti-Pattern CLI
- [ ] Add `cognition patterns antipatterns` command
- [ ] JSON and text output
- [ ] Integration test

---

## Day 7: Integration & Reports

### 7.1 Skill Script
- [ ] Create `scripts/patterns.py` in skill
- [ ] Subcommands: calibration, categories, antipatterns
- [ ] Copy to emerson-workspace skill

### 7.2 Weekly Report
- [ ] Markdown report generator
- [ ] Add to HEARTBEAT.md instructions
- [ ] Proactive alerts when thresholds crossed

### 7.3 Documentation
- [ ] Update SKILL.md with pattern commands
- [ ] Update README with pattern detection section
- [ ] Add usage examples

### 7.4 PR & Review
- [ ] Push branch
- [ ] Create PR via API
- [ ] Spawn code-review sub-agent
- [ ] Address findings
- [ ] Verify CI green
- [ ] Merge when approved

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Brier score calculation | ⬜ |
| Confidence bucket analysis | ⬜ |
| Category success rates | ⬜ |
| Anti-pattern detection | ⬜ |
| CLI commands working | ⬜ |
| Unit tests passing | ⬜ |
| CI green | ⬜ |
| Code review approved | ⬜ |
| Documentation updated | ⬜ |

---

## Progress Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-02-04 | Branch created | ✅ | feature/f002-pattern-detection |
