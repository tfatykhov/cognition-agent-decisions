# F010: Project Context and Outcome Attribution

| Field | Value |
|-------|-------|
| Feature ID | F010 |
| Status | Draft |
| Priority | P1 |
| Depends On | F007 (Record Decision), F008 (Review Decision) |
| Blocks | None |
| Estimated Effort | 5.5h |

## Problem Statement

Currently, decisions lack structured project context. The `context` field is free-form text, making it impossible to:
- Query decisions by project/PR/feature
- Automatically link production bugs to review decisions
- Calculate per-project or per-feature calibration

For code review agents to learn from outcomes, we need structured fields that enable attribution.

## Solution

### Part 1: Extended Schema Fields

Add optional fields to `recordDecision`:

```yaml
# Project context (all optional)
project: "owner/repo"              # GitHub repo identifier
feature: "cstp-feedback-loop"      # Feature/epic name
pr: 8                              # PR number
file: "a2a/cstp/decision_service.py"  # File path
line: 42                           # Line number
commit: "abc123def"                # Commit SHA (short or full)
```

### Part 2: Enhanced Query Filters

Update `queryDecisions` to filter by project context:

```json
{
  "method": "cstp.queryDecisions",
  "params": {
    "query": "error handling",
    "filters": {
      "project": "tfatykhov/cognition-agent-decisions",
      "feature": "cstp-feedback-loop",
      "pr": 8
    }
  }
}
```

### Part 3: Enhanced Calibration Filters

Update `getCalibration` to filter by project context:

```json
{
  "method": "cstp.getCalibration",
  "params": {
    "filters": {
      "project": "tfatykhov/cognition-agent-decisions",
      "feature": "cstp-feedback-loop"
    }
  }
}
```

### Part 4: Outcome Attribution Job

New method or scheduled job that links outcomes to decisions:

```json
{
  "method": "cstp.attributeOutcomes",
  "params": {
    "project": "tfatykhov/cognition-agent-decisions",
    "since": "2026-01-01"
  }
}
```

#### Attribution Logic

1. **PR Stability Check** (automatic)
   - Find PRs merged >14 days ago
   - If no bugs linked → mark all review findings as `success`
   
2. **Bug Linking** (semi-automatic)
   - When bug reported with file:line reference
   - Query decisions matching that file:line
   - If found: mark as `success` (caught) or prompt for review
   - If not found: record as missed bug
   
3. **Git Blame Matching** (automatic)
   - Parse error stack traces for file:line
   - git blame to find introducing commit/PR
   - Match to recorded decisions

## API Changes

### recordDecision (F007) — Extended Params

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| project | string | No | Repository identifier (owner/repo) |
| feature | string | No | Feature or epic name |
| pr | integer | No | Pull request number |
| file | string | No | File path relative to repo root |
| line | integer | No | Line number in file |
| commit | string | No | Commit SHA (7+ chars) |

### queryDecisions (F002) — Extended Filters

| Filter | Type | Description |
|--------|------|-------------|
| project | string | Filter by repository |
| feature | string | Filter by feature name |
| pr | integer | Filter by PR number |
| hasOutcome | boolean | Only reviewed decisions |

### getCalibration (F009) — Extended Filters

| Filter | Type | Description |
|--------|------|-------------|
| project | string | Filter by repository |
| feature | string | Filter by feature name |
| groupBy | string | Add "project" and "feature" options |

### attributeOutcomes — New Method

```json
{
  "method": "cstp.attributeOutcomes",
  "params": {
    "project": "owner/repo",
    "since": "2026-01-01",
    "stabilityDays": 14,
    "dryRun": true
  }
}
```

Response:
```json
{
  "processed": 25,
  "attributed": {
    "stable": 20,
    "bugLinked": 3,
    "missed": 2
  },
  "decisions": [
    {
      "id": "abc123",
      "outcome": "success",
      "reason": "PR stable for 14 days"
    }
  ]
}
```

## Implementation Plan

### Phase 1: Schema Extension (1.5h)
- [ ] Add project context fields to RecordDecisionRequest
- [ ] Update decision_service.py to persist new fields
- [ ] Update tests

### Phase 2: Query Filters (1.5h)
- [ ] Add project/feature/pr filters to QueryDecisionsRequest
- [ ] Update query_service.py filter logic
- [ ] Include new fields in ChromaDB metadata
- [ ] Update tests

### Phase 3: Calibration Filters (1h)
- [ ] Add project/feature filters to GetCalibrationRequest
- [ ] Add groupBy options for project/feature
- [ ] Update calibration_service.py
- [ ] Update tests

### Phase 4: Attribution Job (1.5h)
- [ ] Create attribution_service.py
- [ ] Implement PR stability check
- [ ] Implement file:line matching
- [ ] Add cstp.attributeOutcomes method
- [ ] Update tests

## Example Workflow

### Code Review Agent Records Finding

```json
{
  "method": "cstp.recordDecision",
  "params": {
    "summary": "P1: Missing null check in user validation",
    "confidence": 0.9,
    "category": "code-review",
    "stakes": "high",
    "project": "tfatykhov/cognition-agent-decisions",
    "feature": "cstp-feedback-loop",
    "pr": 8,
    "file": "a2a/cstp/decision_service.py",
    "line": 42,
    "commit": "abc123d"
  }
}
```

### Two Weeks Later: Attribution Runs

```json
{
  "method": "cstp.attributeOutcomes",
  "params": {
    "project": "tfatykhov/cognition-agent-decisions"
  }
}
```

Response:
```json
{
  "attributed": {
    "stable": 15,
    "bugLinked": 1
  },
  "decisions": [
    {
      "id": "finding-abc",
      "outcome": "success",
      "reason": "PR #8 stable for 14 days, no bugs reported"
    }
  ]
}
```

### Calibration Check

```json
{
  "method": "cstp.getCalibration",
  "params": {
    "filters": {
      "project": "tfatykhov/cognition-agent-decisions",
      "category": "code-review"
    }
  }
}
```

## Success Criteria

- [ ] Decisions can be recorded with project context
- [ ] Queries can filter by project/feature/PR
- [ ] Calibration can be calculated per project/feature
- [ ] Attribution job can auto-mark outcomes based on PR stability
- [ ] File:line matching works for bug attribution

## Future Enhancements

- GitHub webhook for real-time bug linking
- Automatic git blame integration
- PR comment parsing for developer feedback
- Dashboard showing per-project calibration trends
