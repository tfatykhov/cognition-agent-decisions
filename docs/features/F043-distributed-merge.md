# F043: Distributed Decision Merge

**Status:** Proposed
**Priority:** Low
**Inspired by:** Beads (steveyegge/beads) - hash-based IDs + git-backed storage for zero-conflict multi-agent merge

## Problem

CSTP is centralized - all agents must be online and connected to the server to record decisions. This creates issues:

- Agents can't record decisions during network outages
- No mechanism for merging decision histories from independent CSTP instances
- Short sequential IDs (8-char hex) can collide across instances
- Multi-team setups require a single shared server

## Solution

Add offline-capable decision recording with content-addressable IDs and a merge protocol for synchronizing independent CSTP instances.

### Content-Addressable IDs

Replace short hex IDs with content-hash-based IDs:

```python
decision_id = sha256(
    agent_id + timestamp + decision_text + category
)[:12]  # "dec-a3f8b2c1d4e5"
```

Benefits:
- Globally unique without coordination
- Deterministic - same decision always gets same ID
- Collision-resistant across instances

### Offline Recording

```
# Agent records locally when server unavailable
cstp.py record --offline -d "decision" -f 0.85 -c arch -s medium
# Stores in local SQLite/JSONL

# Sync when back online
cstp.py sync --server http://192.168.1.141:9991
# Merges local decisions into server, resolves conflicts
```

### Merge Protocol

1. **Export:** `cstp.export` - dump decisions as JSONL with content-hash IDs
2. **Import:** `cstp.import` - ingest external decisions, detect duplicates by hash
3. **Conflict Resolution:**
   - Same hash = duplicate, skip
   - Different hash, same topic = potential `relates_to` link
   - Contradicting decisions = flag for human review

### Federation Sync (extends F038)

```
# Instance A exports to Instance B
cstp.federate --push --target http://other-instance:9991
cstp.federate --pull --source http://other-instance:9991
```

## Phases

1. **P1:** Content-addressable ID generation (backward compatible)
2. **P2:** Offline recording with local SQLite cache
3. **P3:** Sync/merge protocol with conflict detection
4. **P4:** Federation push/pull between CSTP instances

## Integration Points

- F038 (Cross-Agent Federation): Distributed merge is the transport layer for federation
- F039 (Protocol Stack): Merge protocol as part of the CSTP protocol specification
- F040 (Task Graph): Tasks sync alongside decisions
- F042 (Dependencies): Links preserved across merge
