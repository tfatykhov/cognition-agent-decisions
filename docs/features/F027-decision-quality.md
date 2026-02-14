# F027: Decision Recording Quality for Better Retrieval

**Status:** Draft
**Author:** Emerson
**Date:** 2026-02-09

## Problem

Decisions are recorded at an overly operational level, making semantic search return poor results. Typical query distances are 0.5+ (tangential), meaning the pre-decision query step rarely surfaces genuinely useful prior decisions.

### Evidence

```
Query: "adjusting configuration defaults"
Top result distance: 0.300 (barely related)

Query: "infrastructure operational fix"  
Top result distance: 0.234 (wrong decision entirely)
```

Decision text like *"Increased cron run trigger timeout from 60s to 120s"* is so specific that nothing else in the corpus matches. The embedding space is fragmented because every decision uses unique operational language instead of reusable conceptual patterns.

### Root Cause

1. **Decision text is an activity log, not a knowledge base.** We record *what we did* instead of *what we learned*.
2. **Auto-extracted bridges parrot the decision text.** Structure and function fields just copy the decision summary and first reason - no real abstraction.
3. **No cross-cutting metadata.** No tags, themes, or pattern labels to connect decisions across domains.
4. **No guidance on recording quality.** The `record` command accepts anything - there's no nudge toward the right level of abstraction.

## Solution

Three layers: schema changes (tags + pattern fields), better auto-extraction, and agent-side recording guidance.

### Phase 1: Tags & Pattern Fields (Code Change)

Add two new fields to the decision schema:

```yaml
# New fields on RecordDecisionRequest
tags: ["timeout", "defaults", "infrastructure"]  # searchable keywords
pattern: "Override system defaults when they don't match actual workload"  # abstract pattern
```

**Schema changes:**
- `RecordDecisionRequest`: add optional `tags: list[str]` and `pattern: str | None`
- `decision_service.py`: write tags + pattern to YAML, include in ChromaDB metadata
- Tags indexed as ChromaDB metadata (filterable): `metadata["tags"] = ",".join(tags)`
- Pattern embedded alongside decision text for richer semantic matching

**Embedding change:**
Currently `build_embedding_text()` concatenates decision + context + reasons. Add pattern to this:
```python
def build_embedding_text(request):
    parts = [request.decision]
    if request.pattern:
        parts.append(f"Pattern: {request.pattern}")
    if request.context:
        parts.append(request.context)
    # ... reasons
    return " | ".join(parts)
```

**Query changes:**
- `queryDecisions`: support `filters.tags` (match any tag)
- Tag-based search complements semantic search - find all decisions tagged "timeout" regardless of description wording

**CLI changes (`cstp.py`):**
```bash
# Recording with tags and pattern
cstp.py record \
  -d "Increased cron trigger timeout from 60s to 120s" \
  -f 0.90 -c tooling -s low \
  --tag timeout --tag infrastructure --tag defaults \
  --pattern "Override system defaults when they don't match actual workload" \
  -r "empirical:First attempt failed at 60s, succeeded at 120s"

# Querying by tag
cstp.py query "timeout" --tag timeout

# Pre-decision with tag filter
cstp.py pre "fixing a timeout issue" --tag timeout
```

### Phase 2: Smarter Bridge Extraction (Code Change)

Current auto-extraction just copies decision text → structure, first reason → function. Improve to actually abstract:

**Option A: LLM-assisted extraction** (preferred if latency is acceptable)
- On `recordDecision`, call a lightweight LLM (Gemini Flash) to generate:
  - `structure`: "What general pattern does this decision represent?"
  - `function`: "What general class of problem does this solve?"
- Cache/async - don't block the record response

**Option B: Rule-based extraction** (fallback)
- Strip specifics (numbers, names, file paths) from decision text for structure
- Use reason types to infer function category
- Less accurate but zero latency

**Bridge embedding:**
- Embed structure and function separately in ChromaDB as additional documents
- Bridge-side search (`--bridge-side structure/function`) already exists but only works well when bridges contain abstract language

### Phase 3: Recording Quality Score (Code Change)

Add a quality check to `recordDecision` response that scores the recording:

```json
{
  "id": "abc123",
  "quality": {
    "score": 0.65,
    "suggestions": [
      "Decision text is very specific - consider adding a --pattern for the general principle",
      "No tags provided - tags improve cross-domain retrieval",
      "Only 1 reason type used - diverse reasons improve robustness (Minsky Ch 18)"
    ]
  }
}
```

Quality signals:
- Has pattern? (+0.2)
- Has tags? (+0.15)
- Has 2+ distinct reason types? (+0.15)
- Has explicit bridge (not auto-extracted)? (+0.15)
- Decision text length > 20 chars? (+0.1)
- Context provided? (+0.1)
- Has project context? (+0.1)
- Deliberation inputs > 0? (+0.05)

### Phase 4: Agent-Side Process Change (No Code)

Update AGENTS.md recording guidance:

```
When recording decisions, think at TWO levels:
1. OPERATIONAL: What specifically did you do? (the --decision flag)
2. CONCEPTUAL: What pattern does this represent? (the --pattern flag)

Bad:  "Increased cron trigger timeout from 60s to 120s"
Good: "Increased cron trigger timeout from 60s to 120s"
      --pattern "Override system defaults when they don't match actual workload characteristics"
      --tag timeout --tag defaults --tag infrastructure

The decision text is WHAT. The pattern is WHY IT MATTERS for future decisions.
```

## Implementation Plan

| Phase | Effort | Impact | Dependencies |
|-------|--------|--------|-------------|
| P1: Tags + Pattern | ~2 hours | High | Schema + CLI + query changes |
| P2: Better Bridges | ~3 hours | Medium | Gemini API key (already have) |
| P3: Quality Score | ~1 hour | Medium | P1 (checks for tags/pattern) |
| P4: Process Change | ~15 min | High | P1 (needs --tag/--pattern flags) |

**Recommended order:** P1 → P4 → P3 → P2

P1 + P4 together give the biggest bang: tags + patterns make the embedding space denser, and the process change ensures I actually use them. P3 provides ongoing feedback. P2 is a nice-to-have if manual bridges aren't enough.

## Files Changed

### P1
- `a2a/cstp/decision_service.py` - add tags/pattern to schema
- `a2a/cstp/dispatcher.py` - pass through new fields
- `a2a/mcp_server.py` - pass through new fields
- `a2a/cstp/query_service.py` - tag filtering
- `scripts/cstp.py` - CLI flags
- `guardrails/deliberation.yaml` - optional quality guardrail

### P2
- `a2a/cstp/bridge_hook.py` - smarter extraction
- New: `a2a/cstp/llm_bridge.py` - LLM-assisted bridge generation

### P3
- `a2a/cstp/decision_service.py` - quality scorer
- `a2a/cstp/dispatcher.py` - include in response

## Success Metrics

- Average query distance for top-3 results drops from ~0.5 to <0.3
- % of decisions with tags: >80%
- % of decisions with pattern: >60%
- Pre-decision queries actually influence approach (qualitative)

## Open Questions

1. Should tags be free-form or from a controlled vocabulary?
2. Should the quality score be a guardrail (warn if score < 0.5)?
3. Is LLM-assisted bridge extraction worth the latency/cost?
