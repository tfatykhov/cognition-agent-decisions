# F001: OpenClaw Skill Integration - Implementation Checklist

## Day 1: Skill Structure

### 1.1 Create Skill Directory
- [ ] Create `skills/cognition-engines/` in workspace
- [ ] Create `SKILL.md` with metadata
- [ ] Create `scripts/` subdirectory

### 1.2 Query Script
- [ ] `scripts/query.py` - query similar decisions
- [ ] Accept: query text, --top N, --category, --min-confidence
- [ ] Output: JSON with results (title, category, confidence, distance, outcome)
- [ ] Handle ChromaDB connection errors gracefully
- [ ] Test with existing 23 indexed decisions

### 1.3 Check Script  
- [ ] `scripts/check.py` - check guardrails
- [ ] Accept: --category, --stakes, --confidence, --project, etc.
- [ ] Output: JSON with allowed/blocked + violations
- [ ] Load guardrails from default locations
- [ ] Test with cornerstone guardrails

### 1.4 Index Script
- [ ] `scripts/index.py` - index decisions
- [ ] Accept: decisions directory, --incremental
- [ ] Skip already-indexed decisions (by ID)
- [ ] Output: JSON with count indexed
- [ ] Test incremental indexing

### 1.5 SKILL.md Documentation
- [ ] Proper YAML frontmatter (name, description, requires)
- [ ] Usage examples for each script
- [ ] Environment variables documented
- [ ] Installation instructions

---

## Day 2: Auto-Indexing

### 2.1 Post-Decision Hook
- [ ] Modify agent-decisions CLI to call index after logging
- [ ] Or: Create wrapper script that logs + indexes
- [ ] Test: log new decision → verify it appears in query

### 2.2 Incremental Index Logic
- [ ] Track indexed decision IDs in metadata
- [ ] Skip re-indexing on subsequent runs
- [ ] Handle decision updates (re-index if modified)

### 2.3 Integration with Workspace
- [ ] Copy skill to Emerson's workspace `skills/` directory
- [ ] Verify OpenClaw discovers the skill
- [ ] Test natural language invocation

---

## Day 3: Integration Testing

### 3.1 End-to-End Tests
- [ ] Log decision → auto-index → query → find it
- [ ] Check guardrails → blocked → decision not logged
- [ ] Check guardrails → warn → decision logged with warning
- [ ] Query with filters (category, confidence)

### 3.2 Error Handling
- [ ] ChromaDB unavailable → graceful error message
- [ ] Gemini API error → retry with backoff
- [ ] Invalid YAML → clear error message
- [ ] Missing env vars → helpful setup instructions

### 3.3 Documentation
- [ ] Update TOOLS.md with cognition-engines usage
- [ ] Add examples to SKILL.md
- [ ] Create quick-start guide

### 3.4 Verification
- [ ] All scripts work standalone
- [ ] All scripts work via OpenClaw skill invocation
- [ ] CI passes with new tests
- [ ] Emerson actively using for decisions

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Query similar decisions via skill | ⬜ |
| Check guardrails before decisions | ⬜ |
| Auto-index new decisions | ⬜ |
| JSON output for all scripts | ⬜ |
| Works in OpenClaw sandbox | ⬜ |
| Documented in SKILL.md | ⬜ |
| CI green | ⬜ |

---

## Commands Reference

```bash
# Query similar decisions
uv run skills/cognition-engines/scripts/query.py "database choice" --top 5

# Check guardrails
uv run skills/cognition-engines/scripts/check.py --stakes high --confidence 0.4

# Index decisions
uv run skills/cognition-engines/scripts/index.py decisions/ --incremental
```

---

## Progress Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-02-04 | Start implementation | 🟡 | |
