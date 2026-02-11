# F036: Reasoning Continuity

> **Status:** Proposed
> **Target:** v1.0.0 (Multi-Agent Cognition Network)
> **Source:** README roadmap, Minsky Society of Mind (teaching-selves)
> **Depends on:** F035 (Semantic State Transfer), F023 (Deliberation Traces)

## Overview
Enable one agent to "resume" another agent's decision thread. When Agent A starts reasoning about a problem but doesn't finish (session ends, context limits hit, or a specialist is needed), Agent B can pick up exactly where A left off - with full access to A's deliberation trace, query results, and partial conclusions.

## Problem
Today, when a sub-agent is spawned for a task (e.g., code review), it gets a task description but none of the parent agent's cognitive context. The reviewer doesn't know what decisions led to the code, what alternatives were considered, or what guardrails were checked. It starts cold.

## Concept

### Decision Thread
A thread is a chain of linked decisions, deliberation traces, and thoughts:
```
Thread: "PR #94 Architecture"
├── dec_001: "Plan: create feature specs" (emerson)
│   ├── thought: "Checking MIT scaling research..."
│   ├── thought: "4 features map well to findings"
│   └── deliberation: [query results, guardrail checks]
├── dec_002: "Code review PR #94" (code-reviewer)
│   └── continues_thread: dec_001
└── dec_003: "Update docs for PR #94" (docs-agent)
    └── continues_thread: dec_001
```

### Resume Protocol
```json
{
  "method": "cstp.resumeThread",
  "params": {
    "threadId": "thread_pr94",
    "agentId": "code-reviewer",
    "context": "Continuing architecture review started by emerson"
  }
}
```

### Response
```json
{
  "result": {
    "thread": {
      "id": "thread_pr94",
      "title": "PR #94 Architecture",
      "startedBy": "emerson",
      "decisions": [...],
      "openQuestions": ["Should F030 integrate with F032?"],
      "lastState": {
        "conclusion": "4 specs created, pending review",
        "confidence": 0.85,
        "nextSteps": ["Code review", "Documentation"]
      }
    }
  }
}
```

## API

### `cstp.createThread`
Group related decisions into a named thread.

### `cstp.resumeThread`
Load full thread context for continuation by another agent.

### `cstp.getThreadStatus`
Check thread state: active, paused, completed, blocked.

### Enhanced `cstp.recordDecision`
```json
{
  "threadId": "thread_pr94",
  "continuesDecision": "dec_001"
}
```

## Integration
- Uses F023 deliberation traces as the cognitive state to transfer
- Uses F032 error amplification to track chain health
- Uses F035 bundles as the serialization format
- Enables handoffs between specialized agents (architect -> reviewer -> docs)

## Acceptance Criteria
- [ ] `cstp.createThread` RPC method
- [ ] `cstp.resumeThread` RPC method
- [ ] `cstp.getThreadStatus` RPC method
- [ ] Thread linking on `cstp.recordDecision`
- [ ] Full deliberation context loaded on resume
- [ ] MCP tools exposed
- [ ] Dashboard: Thread timeline visualization
