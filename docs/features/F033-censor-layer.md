# F033: Censor Layer - Proactive Failure Pattern Warnings

> **Status:** Proposed
> **Source:** Minsky Society of Mind Ch 27 (Censors and Jokes)
> **Depends on:** Sufficient failure data (~10+ failed/partial decisions)
> **Priority:** Low (blocked by data)
> **Note:** Previously numbered F027; renumbered to avoid conflict with shipped F027 (Decision Quality)

## Concept

Current guardrails are **suppressors** - they block actions at the moment of execution ("high stakes + low confidence = blocked"). Minsky distinguishes these from **censors**, which intercept *before* the bad thought forms.

A censor layer would sit between query and guardrail check:

```
query -> CENSOR (warns based on failure patterns) -> check -> record
```

### Suppressors (what we have)
- Evaluate at action time
- Block based on static rules (stakes/confidence thresholds)
- Reactive - the agent already formulated the bad idea

### Censors (what we'd add)
- Evaluate at query time
- Warn based on *patterns from failed decisions*
- Proactive - deflect before the agent commits to a path

## How It Would Work

1. When `cstp.queryDecisions` returns results, check if any are **failed** or **partial** decisions
2. If failed decisions match the current query context above a threshold, inject a warning:
   ```json
   {
     "results": [...],
     "censors": [
       {
         "source_id": "79462120",
         "pattern": "Skipped mandatory query/check workflow",
         "outcome": "failed",
         "warning": "Similar approach failed before - ensure full workflow compliance"
       }
     ]
   }
   ```
3. The warning is informational (deflect, not block) - the agent can proceed but is made aware

## Activation Criteria

- Minimum 10 failed/partial decisions in corpus
- Failure patterns must be classifiable (not just random one-offs)
- Current corpus: 2 failed, 1 partial (insufficient)

## Key Insight from Minsky

> "Censors avoid waste of time by interceding earlier. Instead of waiting until an action is about to occur, a censor operates earlier, when there still remains time to select alternatives."

> "Sometimes our censors must themselves be suppressed. In order to sketch out long-range plans, we must adopt a style of thought that sets minor obstacles aside."

This means censors should be overridable - useful for exploratory/creative decisions where past failures shouldn't constrain new approaches.

## Related Decisions

- `7ee5358d` - Initial Ch 27 analysis
- `84e7563b` - Deferred knowledge graph (similar "good idea, insufficient data" pattern)
- `5e7b17bb` - Synced guardrails with CSTP server
