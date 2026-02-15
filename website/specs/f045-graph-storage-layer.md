# F045: Decision Graph Storage Layer

**Status:** P1 Implemented
**Priority:** High
**Research basis:** Context Graphs (Masood 2026), Graph-Constrained Reasoning (ICML 2025), MemoBrain (Qian et al. 2026), KnowFlow (Neural Networks 2026), Dual Memory Knowledge Graphs (ScienceDirect 2026)

## Problem

CSTP stores decisions as independent documents with flat `related_to` links discovered via semantic similarity. This misses structural relationships that only a graph can express:

- **No traversal:** Can't follow chains of decisions to find root causes or downstream impacts
- **No centrality:** Can't determine which decisions are structurally important (many dependents) vs peripheral
- **No contradiction detection:** Conflicting active decisions aren't surfaced unless semantically similar
- **No constrained reasoning:** Agents can make decisions that violate the existing dependency structure
- **Compaction is time-based, not salience-based:** Old but structurally critical decisions get summarized equally

CSTP is already 80% of a decision knowledge graph - it has nodes (decisions), edges (related_to), attributes (confidence, outcome, bridge-definitions), and semantic search. Adding a proper graph layer unlocks the remaining 20%.

## Solution

Add a graph storage layer alongside ChromaDB that represents decisions as nodes and their relationships as typed, directed edges. Queries can use graph traversal, semantic search, or both.

### Architecture

```
┌─────────────────────────────────────┐
│           CSTP API Layer            │
├──────────────┬──────────────────────┤
│  ChromaDB    │   Graph Store        │
│  (vectors)   │   (structure)        │
│              │                      │
│  Semantic    │   Traversal          │
│  similarity  │   Centrality         │
│  Bridge      │   Path finding       │
│  search      │   Contradiction      │
│              │   detection          │
└──────────────┴──────────────────────┘
        │               │
        └───── Dual Retrieval ────────┘
              (F024 upgrade)
```

### Graph Model

**Nodes:** Each decision becomes a graph node with properties:
```python
class DecisionNode:
    id: str                    # Decision ID
    category: str
    stakes: str
    confidence: float
    outcome: str | None
    date: str
    tags: list[str]
    pattern: str | None        # Abstract pattern (F027)
    structure_desc: str | None # Bridge structure (F024)
    function_desc: str | None  # Bridge function (F024)
    salience: float            # Computed: graph centrality score
```

**Edges:** Typed, directed relationships between decisions:
```python
class DecisionEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType        # See below
    weight: float              # Strength of relationship
    created_at: datetime
    created_by: str            # Agent or auto-detected
    context: str | None
```

**Edge Types:**
| Type | Direction | Meaning |
|------|-----------|---------|
| `depends_on` | A → B | A required B to exist first |
| `supersedes` | A → B | A replaces B (B is obsolete) |
| `contradicts` | A ↔ B | A and B conflict (bidirectional) |
| `refines` | A → B | A narrows or improves on B |
| `relates_to` | A ↔ B | Topically connected (existing, auto-populated) |
| `caused_by` | A → B | A was a consequence of B's outcome |
| `blocks` | A → B | B cannot proceed until A resolves |

### Storage Backend

**Phase 1: NetworkX (in-process)**
- Zero infrastructure - pure Python, in-memory graph
- Persist as JSONL alongside ChromaDB
- Sufficient for hundreds to low thousands of decisions
- Built-in centrality algorithms (PageRank, betweenness)

**Phase 2: Neo4j (optional, at scale)**
- For deployments with 10K+ decisions or multi-agent federation
- Cypher queries for complex traversal
- Native graph visualization
- Docker-composable with existing CSTP stack

### API

```
# Graph CRUD
cstp.linkDecisions     - Create typed edge between decisions
cstp.unlinkDecisions   - Remove edge
cstp.getGraph          - Get subgraph (node + N hops, optional edge type filter)

# Graph Queries
cstp.findPath          - Shortest path between two decisions
cstp.getAncestors      - All decisions this one depends on
cstp.getDescendants    - All decisions that depend on this one
cstp.findContradictions - Active decisions with contradiction edges
cstp.getBlockedChain   - Decisions blocked by unresolved dependencies

# Salience
cstp.computeSalience   - Recalculate centrality scores for all nodes
cstp.getHighSalience   - Top N structurally important decisions
```

### Dual Retrieval (upgrades F024 Bridge Search)

Current F024 bridge search uses two semantic paths (structure vs function). Graph layer adds a third:

1. **Semantic (vector):** "What decisions are about similar topics?" (ChromaDB)
2. **Structural (graph):** "What decisions are connected to this one?" (Graph traversal)
3. **Hybrid:** Combine both - semantically similar AND structurally connected = highest relevance

```python
def dual_query(query: str, decision_id: str | None = None, hops: int = 2):
    # Semantic results from ChromaDB
    semantic = chromadb.query(query, top_k=10)
    
    # Graph results if we have a starting node
    if decision_id:
        graph_neighbors = graph.get_subgraph(decision_id, hops=hops)
        # Boost decisions that appear in BOTH result sets
        return merge_and_rank(semantic, graph_neighbors)
    
    return semantic
```

### Salience-Based Compaction (upgrades F041)

Instead of time-based decay, use graph centrality to determine compaction priority:

| Salience | Compaction | Reason |
|----------|-----------|--------|
| High (top 20%) | Never compact | Many dependents, structurally critical |
| Medium | Summary after 30 days | Some connections, moderate importance |
| Low (leaf nodes, reviewed) | Digest after 14 days | Peripheral, outcome captured |
| Superseded | Fold into successor immediately | Obsolete by definition |

### Graph-Aware Guardrails (upgrades F030)

New guardrail type: `graph-constraint`

```python
# Block decisions that contradict active high-salience decisions
{
    "name": "no-contradict-high-salience",
    "type": "graph-constraint",
    "rule": "New decision must not contradict any active decision with salience > 0.7",
    "action": "block",
    "message": "This contradicts {conflicting_decision}. Supersede it first."
}
```

### Auto-Edge Detection

When recording a new decision, automatically detect potential edges:
1. Run semantic query for similar decisions
2. Compare patterns and tags for potential `refines` or `contradicts`
3. Check if any active decisions in the same category have opposing outcomes → suggest `contradicts`
4. If decision references another decision's outcome → suggest `caused_by`

## Phases

### P1: Foundation (NetworkX + basic edges)
- NetworkX graph initialized from existing `related_to` data
- `linkDecisions` and `getGraph` API endpoints
- JSONL persistence alongside ChromaDB
- Edge types: `relates_to`, `supersedes`, `depends_on`

### P2: Salience + Dual Retrieval
- PageRank-based salience scoring
- `computeSalience`, `getHighSalience` endpoints
- Dual retrieval: semantic + graph merged results
- Salience field added to query response

### P3: Graph-Aware Guardrails
- `contradicts` and `blocks` edge types
- `findContradictions`, `getBlockedChain` endpoints
- Graph-constraint guardrail type
- Auto-edge detection on `recordDecision`

### P4: Advanced Queries + Visualization
- Path finding, ancestor/descendant traversal
- Graph export for dashboard visualization (D3.js/Cypher)
- Integration with F044 (Work Discovery) - graph-informed ready queue
- Optional Neo4j backend for scale

## Integration Points

- **F002 (Query):** Dual retrieval merges semantic + graph results
- **F024 (Bridge Definitions):** Graph adds structural retrieval path
- **F027 (Decision Quality):** Edge count and diversity as quality signals
- **F030 (Circuit Breakers):** Graph-constraint guardrails
- **F040 (Task Graph):** Tasks as a subgraph connected to decision nodes
- **F041 (Compaction):** Salience-based instead of time-based decay
- **F042 (Dependencies):** F045 subsumes F042 - this IS the dependency graph
- **F043 (Distributed Merge):** Graph edges included in merge protocol
- **F044 (Work Discovery):** Contradictions, blocked chains, low-salience clusters in ready queue

## Research References

1. **Context Graphs** (Masood, 2026) - Governed queryable memory layer connecting entities, decisions, evidence. Explanation packets: answer + evidence paths + provenance.
2. **Graph-Constrained Reasoning** (Luo et al., ICML 2025) - Constrains LLM reasoning to valid knowledge graph paths. KG-Trie structure.
3. **MemoBrain** (Qian et al., 2026) - Dependency-aware memory over reasoning steps. Prunes invalid steps, folds sub-trajectories, preserves reasoning backbone.
4. **KnowFlow** (Neural Networks, 2026) - Knowledge-streamlined agent design. Structured knowledge pipeline consulted before acting.
5. **Dual Memory Knowledge Graph** (ScienceDirect, 2026) - Integrates semantic memory (meaning) with observability memory (what happened). Reduces hallucination.

## Note on F042

F045 subsumes F042 (Decision Dependency Graph). F042 described typed links between decisions; F045 provides the full storage layer, algorithms, and integration. F042 should be marked as "merged into F045" in the index.
