# Feature: OpenClaw Skill Integration

## Overview
Package cognition-agent-decisions as an OpenClaw skill so agents can use semantic decision search and guardrail checks natively.

## User Stories

### US-1: Query Similar Decisions Before Deciding
**As an** AI agent making a decision  
**I want to** query similar past decisions  
**So that** I can learn from prior outcomes and avoid repeating mistakes

**Acceptance Criteria:**
- [ ] Agent can call `cognition.query("context description")`
- [ ] Returns top 5 similar decisions with confidence, outcome, lessons
- [ ] Results include distance score for relevance ranking
- [ ] Works without external API calls (uses existing ChromaDB)

### US-2: Auto-Check Guardrails Before Logging
**As an** AI agent about to log a decision  
**I want to** automatically check guardrails  
**So that** I'm warned or blocked before making policy-violating decisions

**Acceptance Criteria:**
- [ ] Pre-decision hook evaluates all applicable guardrails
- [ ] Block-level violations prevent decision logging
- [ ] Warn-level violations show message but allow proceed
- [ ] Guardrail results logged with decision for audit

### US-3: Index New Decisions Automatically
**As an** AI agent logging decisions  
**I want to** auto-index each decision to the semantic store  
**So that** future queries include my latest decisions

**Acceptance Criteria:**
- [ ] New decisions indexed to ChromaDB on creation
- [ ] Incremental indexing (don't re-index existing)
- [ ] Index includes: title, context, decision, reasons, category, outcome

### US-4: Skill Discovery via SKILL.md
**As an** OpenClaw user  
**I want to** install cognition-engines as a skill  
**So that** my agent gets decision intelligence automatically

**Acceptance Criteria:**
- [ ] SKILL.md with proper metadata
- [ ] Clear usage examples
- [ ] Environment requirements documented
- [ ] Works in OpenClaw sandbox environment

## Technical Requirements

### TR-1: Skill Structure
```
skills/cognition-engines/
├── SKILL.md           # Skill metadata and usage
├── scripts/
│   ├── query.py       # Query similar decisions
│   ├── check.py       # Check guardrails
│   └── index.py       # Index decisions
└── guardrails/
    └── default.yaml   # Default guardrail policies
```

### TR-2: Environment
- GEMINI_API_KEY (for embeddings)
- CHROMA_URL (default: http://chromadb:8000)
- DECISIONS_DIR (default: decisions/)

### TR-3: Integration Points
- Hook into agent-decisions CLI (post-log indexing)
- Expose as standalone scripts for OpenClaw
- Return structured JSON for programmatic use

## API Design

### Query API
```bash
# CLI
cognition query "choosing a database for vector storage" --top 5

# Python
from cognition_engines import query_similar
results = query_similar("choosing a database", n=5)
```

**Response:**
```json
{
  "query": "choosing a database for vector storage",
  "results": [
    {
      "title": "Use ChromaDB for semantic memory",
      "category": "architecture",
      "confidence": 0.85,
      "outcome": "success",
      "distance": 0.42,
      "lessons": "Works well for <100k vectors"
    }
  ]
}
```

### Check API
```bash
# CLI
cognition check --category architecture --stakes high --confidence 0.4

# Python
from cognition_engines import check_guardrails
result = check_guardrails(category="architecture", stakes="high", confidence=0.4)
```

**Response:**
```json
{
  "allowed": false,
  "violations": [
    {
      "guardrail": "no-high-stakes-low-confidence",
      "action": "block",
      "message": "High-stakes decisions require ≥50% confidence"
    }
  ]
}
```

### Index API
```bash
# CLI
cognition index decisions/ --incremental

# Python
from cognition_engines import index_decision
index_decision(decision_dict)
```

## Out of Scope (v0.6.0)
- Cross-agent federation (v0.7.0)
- Web dashboard
- Pattern detection alerts
- Outcome tracking automation
