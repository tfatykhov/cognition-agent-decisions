# F049: Live Deliberation Viewer

**Status:** Proposed
**Priority:** P1
**Depends on:** F028 (Reasoning Capture), F045 (Graph Storage), debugTracker endpoint

## Problem

Agents accumulate deliberation traces (thoughts, queries, guardrail checks) in the tracker before recording decisions. Today, the only way to inspect this is via `cstp.debugTracker` JSON-RPC - a raw JSON dump with no visual structure. When multiple agents share an MCP connection, it's hard to understand:

- Which agents are actively deliberating
- How many thoughts have accumulated per decision
- Whether thoughts are being consumed correctly on `recordDecision`
- The real-time flow from thought → decision → review

Operators need a live view to monitor agent cognition, debug isolation issues, and verify the deliberation pipeline works end-to-end.

## Solution

Add a **Live Deliberation** page to the dashboard that shows real-time tracker state with auto-refresh, organized by agent and decision.

## UI Design

### Page Layout

```
┌─────────────────────────────────────────────────────┐
│  🧠 Live Deliberation                    ⟳ Auto 5s  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Active Sessions: 3          Total Thoughts: 12     │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🟢 agent:planner:decision:abc123            │    │
│  │    4 thoughts · 45s ago                     │    │
│  │  ┌─────────────────────────────────────┐    │    │
│  │  │ r-0292d47a · reasoning · 45s ago    │    │    │
│  │  │ "Considering approach A vs B..."    │    │    │
│  │  ├─────────────────────────────────────┤    │    │
│  │  │ r-81e0aacd · reasoning · 38s ago    │    │    │
│  │  │ "Approach B better for isolation"   │    │    │
│  │  ├─────────────────────────────────────┤    │    │
│  │  │ r-f3a1b2c4 · query · 30s ago       │    │    │
│  │  │ "Found 3 similar decisions..."      │    │    │
│  │  ├─────────────────────────────────────┤    │    │
│  │  │ r-d5e6f7a8 · guardrail · 25s ago   │    │    │
│  │  │ "Guardrail check passed"            │    │    │
│  │  └─────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🟢 agent:architect:decision:def456          │    │
│  │    2 thoughts · 12s ago                     │    │
│  │  ...                                        │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ 🟡 mcp-session (no agent_id)               │    │
│  │    6 thoughts · 2m ago                      │    │
│  │  ...                                        │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ── Recently Consumed ──────────────────────────    │
│  ✅ agent:dev:decision:ghi789 → decision 01cab3    │
│     3 thoughts consumed · 5m ago                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Key Visual Elements

1. **Session cards** - one per tracker key, color-coded:
   - 🟢 Active (thoughts < 60s old)
   - 🟡 Stale (thoughts > 60s old)
   - 🔴 Very stale (> 5min, likely orphaned)

2. **Thought timeline** - chronological list within each card:
   - Type badge (reasoning, query, guardrail)
   - Truncated text with expand-on-click
   - Relative timestamp

3. **Composite key breakdown** - parse and display:
   - Agent name (from `agent:{name}`)
   - Decision ID (from `decision:{id}`, linked to decision detail page)
   - Warning icon for bare `mcp-session` keys (no isolation)

4. **Recently consumed section** - show tracker keys that were cleared by `recordDecision` in the last 10 minutes, with link to the resulting decision

5. **Auto-refresh** - HTMX polling every 5s (configurable), with visual pulse on new thoughts

## API Requirements

### Existing: `cstp.debugTracker`

Already returns the needed data:

```json
{
  "sessions": ["agent:planner:decision:abc123", ...],
  "sessionCount": 3,
  "detail": {
    "agent:planner:decision:abc123": {
      "key": "agent:planner:decision:abc123",
      "inputCount": 4,
      "inputs": [
        {
          "id": "r-0292d47a",
          "type": "reasoning",
          "text": "Considering approach A vs B...",
          "source": "cstp:recordThought",
          "ageSeconds": 45
        }
      ]
    }
  }
}
```

### New: Consumption History (optional, P2)

Track last N consumed tracker sessions for the "Recently Consumed" section:

```json
{
  "method": "cstp.debugTracker",
  "params": {
    "include_consumed": true,
    "consumed_limit": 10
  }
}
```

Returns additional `consumed` array with `{ key, thoughtCount, consumedAt, decisionId }`.

## Implementation

### Dashboard Changes

1. **Route:** `GET /deliberation` → `deliberation()` view
2. **Template:** `templates/deliberation.html`
3. **Partial:** `templates/deliberation_partial.html` (HTMX swap target)
4. **Nav:** Add sidebar link with 🔮 icon
5. **Client:** `cstp_client.py` add `debug_tracker()` method
6. **Auto-refresh:** `hx-get="/deliberation/partial" hx-trigger="every 5s" hx-swap="innerHTML"`

### CSS

- Reuse existing card styles from overview/decisions pages
- Add type badges (reasoning=blue, query=green, guardrail=yellow)
- Pulse animation for new thoughts (CSS `@keyframes`)
- Collapsible thought text (Alpine.js `x-show`)

### Tech Stack

Same as existing dashboard:
- Flask + Jinja2
- HTMX for partial updates
- Alpine.js for interactive elements
- Chart.js (optional, for thought rate sparkline)

## Checklist

- [ ] Add `debug_tracker()` to `cstp_client.py`
- [ ] Create `deliberation.html` template
- [ ] Create `deliberation_partial.html` for HTMX refresh
- [ ] Add `/deliberation` route to `app.py`
- [ ] Add sidebar nav link
- [ ] Parse composite keys for display (agent name, decision link)
- [ ] Color-code by age (active/stale/orphaned)
- [ ] Type badges for thought sources
- [ ] Auto-refresh with HTMX polling
- [ ] Expand/collapse thought text
- [ ] Add to dashboard tests
- [ ] P2: Consumption history tracking in server
- [ ] P2: "Recently Consumed" section
- [ ] P2: Thought rate sparkline chart

## Testing

- Mock `debugTracker` response in dashboard tests
- Test composite key parsing (`agent:x:decision:y` → agent="x", decision="y")
- Test empty state (no active sessions)
- Test stale detection (age thresholds)

## Security

- Dashboard auth required (existing `auth.py`)
- Thought text may contain sensitive reasoning - same access level as decision detail
- No new CSTP auth changes needed (reuses dashboard token)
