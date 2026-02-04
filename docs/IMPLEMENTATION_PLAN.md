# Implementation Plan: v0.6.0

## Overview
Make cognition-agent-decisions a usable OpenClaw skill that Emerson runs on daily.

**Timeline:** 2 weeks  
**Goal:** Emerson actively uses cognition-engines for every decision

---

## Phase 1: OpenClaw Skill (Days 1-3)

### Day 1: Skill Structure
- [ ] Create `skills/cognition-engines/SKILL.md`
- [ ] Write standalone scripts: `query.py`, `check.py`, `index.py`
- [ ] Add JSON output mode for all scripts
- [ ] Test in OpenClaw sandbox

### Day 2: Auto-Indexing
- [ ] Hook into decision creation flow
- [ ] Incremental indexing (skip already indexed)
- [ ] Add `--auto-index` flag to agent-decisions CLI
- [ ] Verify 23 existing decisions indexed correctly

### Day 3: Integration Testing
- [ ] End-to-end: log decision → auto-index → query → find it
- [ ] Guardrail check before logging decision
- [ ] Document usage in SKILL.md
- [ ] Add to Emerson's TOOLS.md

**Deliverables:**
- Working OpenClaw skill
- Auto-indexing on decision creation
- Emerson can query/check via natural commands

---

## Phase 2: Pattern Detection (Days 4-7)

### Day 4: Calibration Report
- [ ] Implement `PatternDetector.calibration_report()`
- [ ] Brier score calculation
- [ ] Confidence bucket analysis
- [ ] CLI: `cognition patterns calibration`

### Day 5: Category Analysis
- [ ] Implement `PatternDetector.category_analysis()`
- [ ] Success rate by category
- [ ] Low-confidence category alerts
- [ ] CLI: `cognition patterns categories`

### Day 6: Anti-Pattern Detection
- [ ] Implement `PatternDetector.anti_patterns()`
- [ ] Repeated failures detection
- [ ] Flip-flop detection (contradictory decisions)
- [ ] CLI: `cognition patterns antipatterns`

### Day 7: Weekly Report Integration
- [ ] Generate markdown report
- [ ] Add to HEARTBEAT.md for weekly review
- [ ] Proactive alerts when thresholds crossed

**Deliverables:**
- Pattern detection engine
- Calibration, category, anti-pattern reports
- Weekly review automation

---

## Phase 3: Enhanced Guardrails (Days 8-10)

### Day 8: Guardrail v2 Parser
- [ ] Extend YAML schema for v2 conditions
- [ ] Semantic similarity condition evaluator
- [ ] Temporal condition evaluator
- [ ] Backward compatible with v1

### Day 9: Audit Trail
- [ ] Log guardrails evaluated per decision
- [ ] Query by violation
- [ ] Export audit report
- [ ] Add to decision YAML output

### Day 10: Templates
- [ ] Create production-safety template
- [ ] Create financial template
- [ ] CLI: `cognition guardrails apply-template`
- [ ] Document templates

**Deliverables:**
- Guardrail v2 with rich conditions
- Audit trail for all decisions
- Reusable templates

---

## Phase 4: Dogfooding & Polish (Days 11-14)

### Day 11-12: Active Usage
- [ ] Emerson uses cognition-engines for all new decisions
- [ ] Query similar before each decision
- [ ] Check guardrails before logging
- [ ] Document friction points

### Day 13: Fixes & Improvements
- [ ] Address friction from dogfooding
- [ ] Performance optimization if needed
- [ ] Error handling improvements
- [ ] Better error messages

### Day 14: Release
- [ ] Update README with v0.6.0 features
- [ ] Generate new architecture diagram
- [ ] Tag v0.6.0 release
- [ ] Post to Moltbook m/builds

**Deliverables:**
- Production-ready v0.6.0
- Active usage by Emerson
- Public release announcement

---

## Success Criteria

### Must Have (v0.6.0)
- [ ] Query similar decisions via skill
- [ ] Guardrail checks before decisions
- [ ] Auto-index new decisions
- [ ] Calibration report

### Should Have
- [ ] Category analysis
- [ ] Anti-pattern detection
- [ ] Guardrail audit trail

### Nice to Have
- [ ] Guardrail templates
- [ ] Proactive alerts
- [ ] Weekly report automation

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ChromaDB unavailable | High | Graceful fallback, skip indexing |
| Gemini rate limits | Medium | Cache embeddings, batch requests |
| Complex YAML parsing | Medium | Keep v1 compatibility, add v2 incrementally |
| Low decision count | Low | Works with 10+ decisions for basic patterns |

---

## Daily Standup Check

Each day, Emerson should:
1. Check previous day's deliverables
2. Run tests before new work
3. Commit progress end of day
4. Update this plan with actuals

---

## Notes

- Priority: Skill integration first (must be usable)
- Pattern detection: analytical, not blocking
- Guardrails v2: incremental enhancement
- Dogfooding: critical for finding real issues
