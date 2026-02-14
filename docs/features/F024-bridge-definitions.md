# F024: Bridge-Definitions for Decisions

**Status:** Proposed
**Origin:** Minsky, Society of Mind, Ch 12.13 (Bridge-Definitions)
**Author:** Emerson
**Date:** 2026-02-08

## Core Insight

> "Our best ideas are often those that bridge between two different worlds!"
> - Minsky, 12.13

A decision has two faces:
- **Structure** - what pattern was used, what it looks like (files, tools, code shapes, configurations)
- **Function** - what problem it solves, what purpose it serves (goals, constraints, tradeoffs)

Today CSTP stores a flat `decision` text and `context`. These mix structure and function together, making it hard to search from either direction. Bridge-definitions separate them so you can query:
- "I see this pattern (structure) - what is it for?" (structure -> function)
- "I have this problem (function) - what patterns solve it?" (function -> structure)

## Design

### Phase 1: Schema + Storage

Add two optional fields to `RecordDecisionRequest`:

```python
@dataclass
class BridgeDefinition:
    """Minsky Ch 12 bridge-definition: connects structure to function."""
    structure: str          # What it looks like / recognizable pattern
    function: str           # What problem it solves / purpose
    tolerance: list[str]    # Features that DON'T matter (Ch 12.3)
    enforcement: list[str]  # Features that MUST be present (Ch 12.3)
    prevention: list[str]   # Features that MUST NOT be present (Ch 12.3)
```

**Usage in record call:**
```json
{
  "decision": "Used fail-open pattern for deliberation tracking",
  "bridge": {
    "structure": "try/except around telemetry calls, catch Exception, log debug, return default",
    "function": "prevent observability failures from breaking core API paths",
    "tolerance": ["log level", "specific exception types", "return value shape"],
    "enforcement": ["must catch all exceptions", "must log for debugging", "must return safe default"],
    "prevention": ["must not swallow errors silently without logging", "must not re-raise"]
  }
}
```

**YAML output:**
```yaml
bridge:
  structure: "try/except around telemetry calls, catch Exception, log debug, return default"
  function: "prevent observability failures from breaking core API paths"
  tolerance:
    - "log level"
    - "specific exception types"
  enforcement:
    - "must catch all exceptions"
    - "must log for debugging"
  prevention:
    - "must not swallow errors silently"
```

### Phase 2: Dual Indexing

Index both `structure` and `function` into ChromaDB embeddings so queries from either side find matches.

Update `build_embedding_text()`:
```python
if request.bridge:
    parts.append(f"Structure: {request.bridge.structure}")
    parts.append(f"Function: {request.bridge.function}")
```

Add query filter `bridgeSide`:
- `"structure"` - boost structure field similarity (I recognize this pattern)
- `"function"` - boost function field similarity (I need to solve this problem)
- `"both"` (default) - search across both equally

### Phase 3: Auto-Extraction (Optional)

For decisions recorded without explicit bridge fields, use the existing `decision` + `context` + `reasons` to auto-extract structure/function:

- Structure hints: file paths, tool names, code patterns, configuration details
- Function hints: "to solve", "to prevent", "to enable", reason text

This could be a background job that enriches older decisions, or a real-time extraction during `recordDecision`.

### Phase 4: Bridge Analytics

New endpoint `cstp.getBridgeStats`:
- Most reusable structures (patterns that solve multiple problems)
- Most common functions (problems solved by multiple patterns)
- Orphan structures (patterns without clear function)
- Orphan functions (problems without known patterns)
- Bridge strength: how often a structure-function pair leads to success

## Implementation Plan

### Phase 1 (Core - 1 PR)

1. **`BridgeDefinition` dataclass** in `decision_service.py`
   - Fields: `structure`, `function`, `tolerance`, `enforcement`, `prevention`
   - `from_dict()` / `to_dict()` methods
   - All fields optional strings/lists

2. **Add `bridge` field to `RecordDecisionRequest`**
   - Optional `BridgeDefinition | None`
   - Parse from `bridge` key in JSON-RPC params
   - Support both camelCase and snake_case

3. **YAML persistence**
   - Add `bridge:` section to decision YAML output
   - Backward compatible - old decisions without bridge still work

4. **MCP schema**
   - Add `BridgeSchema` to `mcp_schemas.py`
   - Wire into `log_decision` tool input

5. **Embedding text**
   - Include structure + function in `build_embedding_text()`
   - Weight structure and function equally

6. **CLI**
   - `cstp.py record --structure "..." --function "..."`
   - Optional `--tolerance`, `--enforcement`, `--prevention`

7. **Tests**
   - Bridge parsing, YAML round-trip, embedding inclusion

### Phase 2 (Search - 1 PR)

8. **Query filter `bridgeSide`**
   - Add to `QueryFiltersInput` and `_build_query_params()`
   - When `bridgeSide=structure`, prepend "Structure: " to query for embedding similarity
   - When `bridgeSide=function`, prepend "Function: " to query

9. **`cstp.getDecision` response**
   - Include full bridge in decision detail

### Phase 3 (Auto-Extract - 1 PR, optional)

10. **Heuristic extractor**
    - Regex/keyword-based extraction from decision text + context
    - Run on `recordDecision` if no explicit bridge provided
    - Mark as `bridge_auto: true` (like deliberation_auto)

### Phase 4 (Analytics - 1 PR, optional)

11. **`cstp.getBridgeStats` endpoint**
    - Most reused structures/functions
    - Bridge strength (success correlation)

## Compatibility

- Fully backward compatible - bridge is optional
- Old decisions without bridge still query normally
- New decisions with bridge get richer search results
- No breaking changes to existing API

## Relation to Other Features

- **F023 (Deliberation Traces):** Deliberation captures HOW you decided. Bridge captures WHAT you decided in dual form.
- **F020 (Reasoning Trace):** Reasoning trace is sequential steps. Bridge is a static dual description.
- **Ch 18 (Parallel Bundles):** Reasons are parallel evidence. Bridge connects that evidence to outcomes.
- **Ch 21 (Pronomes):** Pronomes separate assignment from action. Bridge separates structure from function.

## Open Questions

1. Should `tolerance/enforcement/prevention` be in Phase 1 or deferred? They add richness but also complexity.
2. Should auto-extraction (Phase 3) be opt-in or default?
3. Should we retroactively enrich existing decisions?
