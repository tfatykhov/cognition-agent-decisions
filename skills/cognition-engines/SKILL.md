---
name: cognition-engines
description: Decision intelligence for AI agents. Query similar past decisions, check guardrails before deciding, and auto-index decisions for semantic search.
homepage: https://github.com/tfatykhov/cognition-agent-decisions
metadata:
  openclaw:
    emoji: "🧠"
    requires:
      env:
        - GEMINI_API_KEY
    primaryEnv: GEMINI_API_KEY
---

# Cognition Engines

Decision intelligence for AI agents. Query similar past decisions before making new ones, check guardrails to prevent policy violations, and build a searchable decision memory.

## Quick Start

### Query Similar Decisions
Find past decisions similar to your current context:
```bash
uv run {baseDir}/scripts/query.py "choosing a database for vector storage" --top 5
```

### Check Guardrails
Verify a decision doesn't violate policies before logging:
```bash
uv run {baseDir}/scripts/check.py --category architecture --stakes high --confidence 0.8
```

### Index Decisions
Index decision YAML files for semantic search:
```bash
uv run {baseDir}/scripts/index.py /path/to/decisions/ --incremental
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key for embeddings |
| `CHROMA_URL` | No | `http://chromadb:8000` | ChromaDB server URL |
| `DECISIONS_DIR` | No | `decisions/` | Default decisions directory |

## Usage Examples

### Before Making a Decision
```bash
# 1. Query similar past decisions
uv run {baseDir}/scripts/query.py "should we use microservices or monolith"

# 2. Check if guardrails allow this decision
uv run {baseDir}/scripts/check.py --category architecture --stakes high --confidence 0.75

# 3. If allowed, log your decision (via agent-decisions)
# 4. Auto-index happens on logging
```

### Output Format
All scripts output JSON for programmatic use:

**Query:**
```json
{
  "query": "database choice",
  "results": [
    {
      "title": "Use ChromaDB for semantic memory",
      "category": "architecture",
      "confidence": 0.85,
      "outcome": "success",
      "distance": 0.42
    }
  ]
}
```

**Check:**
```json
{
  "allowed": true,
  "evaluated": 3,
  "violations": []
}
```

## Guardrails

Default guardrails are in `guardrails/default.yaml`. Cornerstone rules:

- **no-production-without-review**: Block production changes without code review
- **no-high-stakes-low-confidence**: Block high-stakes decisions with <50% confidence
- **no-trading-without-backtest**: Block trading strategy changes without backtesting

## Integration

This skill works best with:
- **agent-decisions**: Decision logging framework
- **ChromaDB**: Vector database for semantic search
- **OpenClaw**: AI agent runtime

## Troubleshooting

**ChromaDB connection error:**
- Verify `CHROMA_URL` is correct
- Check if ChromaDB container is running

**No results from query:**
- Run `index.py` first to index your decisions
- Check `DECISIONS_DIR` points to correct location

**Guardrail not triggering:**
- Verify condition fields match your context keys
- Check guardrail YAML syntax
