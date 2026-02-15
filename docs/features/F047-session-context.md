# F047: Session Context Endpoint

**Status:** Shipped (v0.11.0)
**Priority:** High
**Category:** Agentic Loop Integration

## Problem

Agents starting a new session have no cognitive context. They don't know:
- What decisions were made previously in this domain
- What their calibration profile looks like (am I overconfident? in which areas?)
- What guardrails are active
- What cognitive maintenance is overdue (unreviewed decisions, calibration drift)

Loading this context requires multiple API calls and manual system prompt construction. Most frameworks don't bother - agents start cold every time.

## Solution

A single `cstp.getSessionContext` endpoint that returns everything an agent needs to be cognitively aware at session start. Designed for injection into system prompts or agent initialization.

### API

```json
{
  "method": "cstp.getSessionContext",
  "params": {
    "agent_id": "claude-code",
    "task_description": "Build authentication service for user API",
    "include": ["decisions", "guardrails", "calibration", "ready", "patterns", "contradictions"],
    "decisions_limit": 10,
    "ready_limit": 5,
    "format": "markdown"
  }
}
```

### Response (format: "json")

```json
{
  "result": {
    "agent_profile": {
      "agent_id": "claude-code",
      "total_decisions": 47,
      "reviewed": 32,
      "overall_accuracy": 0.94,
      "brier_score": 0.028,
      "tendency": "slightly_underconfident",
      "strongest_category": "tooling",
      "weakest_category": "security",
      "active_since": "2026-01-15"
    },

    "relevant_decisions": [
      {
        "id": "dec-7e2f",
        "decision": "Chose JWT for API auth",
        "outcome": "success",
        "date": "2026-01-15",
        "pattern": "Stateless auth scales better",
        "tags": ["auth", "jwt", "architecture"]
      }
    ],

    "active_guardrails": [
      {
        "name": "no-high-stakes-low-confidence",
        "description": "Block if stakes=high and confidence < 0.5",
        "action": "block"
      },
      {
        "name": "no-production-without-review",
        "description": "Require code review for production changes",
        "action": "warn"
      }
    ],

    "calibration_by_category": {
      "architecture": { "accuracy": 0.93, "brier": 0.03, "decisions": 18, "tendency": "well_calibrated" },
      "security": { "accuracy": 0.80, "brier": 0.08, "decisions": 5, "tendency": "overconfident" }
    },

    "ready_queue": [
      {
        "type": "review_outcome",
        "priority": "high",
        "decision_id": "dec-b1c2",
        "reason": "Architecture decision from 12 days ago, no outcome recorded"
      }
    ],

    "confirmed_patterns": [
      { "pattern": "Stateless auth scales better than session-based", "confirmations": 3, "category": "architecture" },
      { "pattern": "Always validate input at API boundary", "confirmations": 5, "category": "security" }
    ],

    "active_contradictions": []
  }
}
```

### Response (format: "markdown")

When `format: "markdown"`, returns a pre-formatted block ready for system prompt injection:

```json
{
  "result": {
    "markdown": "## CSTP Decision Context\n\n### Your Profile\n- 47 decisions logged, 94% accuracy, Brier 0.028\n- ⚠️ Tendency: slightly underconfident (raise confidence in architecture)\n- ⚠️ Weak area: security (80% accuracy, 5 decisions)\n\n### Relevant Past Decisions\n| Decision | Outcome | Date | Pattern |\n|----------|---------|------|---------|\n| Chose JWT for API auth | ✅ success | 2026-01-15 | Stateless auth scales better |\n...\n\n### Active Guardrails\n- 🚫 no-high-stakes-low-confidence: Block if stakes=high, confidence < 0.5\n- ⚠️ no-production-without-review: Warn on production changes without review\n\n### Pending Tasks\n- ❗ Review outcome for dec-b1c2 (architecture, 12 days overdue)\n\n### Confirmed Patterns\n- Stateless auth scales better (3x confirmed)\n- Always validate input at API boundary (5x confirmed)\n\n### Decision Protocol\nUse `pre_action` tool before any significant decision.\nInclude: confidence, category, stakes, 2+ reasons, tags, pattern."
  }
}
```

### Use Cases

**1. Claude Code CLI - system prompt injection:**
```markdown
# In CLAUDE.md (auto-generated or templated)
{{cstp_session_context}}
```

A build script or pre-hook calls `getSessionContext` and injects the markdown into CLAUDE.md before the session starts.

**2. OpenClaw - agent initialization:**
```python
# In agent startup
context = await cstp.get_session_context(
    agent_id="emerson",
    task_description=current_task,
    format="markdown"
)
system_prompt += context["markdown"]
```

**3. LangChain / CrewAI / AutoGen:**
```python
# As a tool or system message
context = cstp_client.get_session_context(agent_id="agent-1", task="...")
agent = Agent(system_message=base_prompt + context.markdown)
```

**4. Periodic refresh (long sessions):**
Call `getSessionContext` every N turns to refresh decisions and ready queue as the session evolves.

### MCP Tool Definition

```json
{
  "name": "get_session_context",
  "description": "Get full cognitive context for this session: relevant past decisions, calibration profile, active guardrails, pending tasks, and confirmed patterns. Call at session start or when switching tasks.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_description": { "type": "string", "description": "What you're working on this session" },
      "include": {
        "type": "array",
        "items": { "type": "string", "enum": ["decisions", "guardrails", "calibration", "ready", "patterns", "contradictions"] },
        "default": ["decisions", "guardrails", "calibration", "ready", "patterns"]
      },
      "decisions_limit": { "type": "integer", "default": 10 },
      "ready_limit": { "type": "integer", "default": 5 },
      "format": { "type": "string", "enum": ["json", "markdown"], "default": "markdown" }
    },
    "required": ["task_description"]
  }
}
```

## Design Principles

- **Session-level, not decision-level.** F046 (preAction) is called per decision. F047 is called once at session start (or on task switch).
- **Markdown-first.** Most agent frameworks inject context as text. The markdown format is ready to paste into any system prompt.
- **Progressive disclosure.** The `include` array lets lightweight agents request only what they need. Full context for complex agents, just guardrails for simple ones.
- **Framework-agnostic.** JSON-RPC + MCP. Works with Claude Code, OpenClaw, LangChain, CrewAI, raw curl.

## Phases

1. **P1:** Core endpoint - decisions + guardrails + calibration
2. **P2:** Ready queue + patterns + contradictions
3. **P3:** Markdown formatting + MCP tool
4. **P4:** Auto-refresh middleware for long sessions

## Integration Points

- F002 (Query): Task-scoped decision retrieval
- F003 (Guardrails): Active guardrail listing
- F009 (Calibration): Per-agent, per-category calibration
- F027 (Quality): Confirmed patterns from quality-scored decisions
- F044 (Work Discovery): Ready queue integration
- F045 (Graph): Graph-neighbor decisions in context
- F046 (Pre-Action): Session context is the complement - F047 loads context, F046 gates individual decisions
