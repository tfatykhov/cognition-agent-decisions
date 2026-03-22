# F054 — Decision Admission Gate

> **Status:** Draft v1
> **Priority:** P1
> **Depends on:** F027 (Decision Quality), F050 (SQLite Storage)
> **Addresses:** Decision logging pollution — 33% of recorded decisions are status updates, not actual decisions (Tier 2 review, 2026-03-22)

---

## Problem Statement

Agents record status updates, informational outputs, and conversational fragments as decisions. Observed in Nous (16/54 decisions were noise in one week), but affects any agent using CSTP.

### Examples of Pollution

| Recorded as "decision" | Actually is |
|------------------------|-------------|
| "✅ Done! Email sent to Maya with article changes" | Status update |
| "F023 is live! Here's what I can see..." | Explanation |
| "Good news — this is already designed in F022" | Informational |
| "Plan: Update minsky-nous-mapping.md" (never executed) | Abandoned intent |
| "Here are the sweep results..." | Data presentation |

### Impact

- Inflates failure rate (noise decisions get reviewed as "failed")
- Distorts calibration (Brier scores polluted by non-decisions)
- Wastes reviewer time (Tier 2 review spends 30%+ on noise)
- Degrades semantic search (queries return noise alongside real decisions)
- Embedding centroids drift toward noise patterns

### Why the Current Quality Gate Doesn't Catch This

F027's quality gate checks for structural completeness: tags, pattern, reasons. An agent can attach tags and a pattern to "✅ Done! Email sent..." and pass the gate. The gate checks *form*, not *substance*.

---

## Solution: Three-Layer Admission Gate

The gate runs inside `recordDecision` before the decision is persisted. Three layers, each independent, scored and combined.

```
recordDecision(text, context)
       │
       ▼
  ┌─────────────┐
  │   Layer 1    │  Structural Signal Scoring
  │  (instant)   │  Score: 0.0 - 1.0
  └──────┬───────┘
         │
         ▼
  ┌─────────────┐
  │   Layer 2    │  Embedding Classifier
  │  (~5ms)      │  Score: 0.0 - 1.0
  └──────┬───────┘
         │
         ▼
  ┌─────────────┐
  │   Layer 3    │  LLM Gate (Haiku)
  │  (~1-2s)     │  Only if Layers 1+2 disagree
  └──────┬───────┘
         │
    ┌────┴────┐
    ▼         ▼
 ACCEPT    REJECT
           (with reason)
```

### Layer 1: Structural Signal Scoring

Zero-cost, instant. Scores the *shape* of the decision, not its text.

```python
def structural_score(decision: dict, tracker_state: dict | None) -> float:
    """Score how much this looks like a real decision (0.0 - 1.0).
    
    Real decisions have: deliberation trace, diverse reasoning,
    alternatives considered, calibrated confidence, quality metadata.
    Status updates have: none of these.
    """
    score = 0.0
    weights = {}
    
    # 1. Deliberation trace exists (query + guardrail check preceded this)
    #    This is the strongest signal. Real decisions go through pre_action.
    #    Status updates are ad-hoc record calls.
    if tracker_state and tracker_state.get("deliberation_inputs"):
        inputs = tracker_state["deliberation_inputs"]
        if inputs.get("similar_decisions_queried"):
            score += 0.15
            weights["query_trace"] = 0.15
        if inputs.get("guardrails_checked"):
            score += 0.15
            weights["guardrail_trace"] = 0.15
    
    # 2. Reasoning diversity
    #    Real decisions have multiple reason types (analysis + empirical).
    #    Status updates have zero or one.
    reasons = decision.get("reasons", [])
    reason_types = set(r.get("type", "") for r in reasons)
    if len(reason_types) >= 2:
        score += 0.20
        weights["reason_diversity"] = 0.20
    elif len(reason_types) == 1:
        score += 0.05
        weights["reason_diversity"] = 0.05
    
    # 3. Alternatives or trade-offs mentioned
    #    Decisions involve choosing. Status updates don't.
    text = decision.get("decision", "").lower()
    context = (decision.get("context") or "").lower()
    alt_signals = ["instead of", "rather than", "alternative", "trade-off",
                   "tradeoff", "option", "chose", "decided against",
                   "considered", "weighed", "vs", "over"]
    if any(s in text or s in context for s in alt_signals):
        score += 0.15
        weights["alternatives"] = 0.15
    
    # 4. Confidence is calibrated (not a default/lazy value)
    #    0.5 and 1.0 are the two most common lazy defaults.
    #    Real decisions land on specific values (0.72, 0.85, 0.91).
    conf = decision.get("confidence", 0.5)
    if conf not in (0.0, 0.5, 1.0):
        score += 0.10
        weights["calibrated_confidence"] = 0.10
    
    # 5. Quality metadata (tags + pattern)
    #    F027 already checks this, but its presence is a positive signal.
    has_tags = bool(decision.get("tags"))
    has_pattern = bool(decision.get("pattern"))
    if has_tags and has_pattern:
        score += 0.15
        weights["quality_metadata"] = 0.15
    elif has_tags or has_pattern:
        score += 0.05
        weights["quality_metadata"] = 0.05
    
    # 6. Stakes are specified and non-default
    stakes = decision.get("stakes", "")
    if stakes and stakes != "low":
        score += 0.10
        weights["stakes_specified"] = 0.10
    
    return min(score, 1.0), weights
```

**Scoring properties:**
- A decision that went through full CSTP workflow (query → check → record with diverse reasons, tags, pattern): **0.85-1.0**
- A decision recorded with some metadata but no deliberation: **0.30-0.50**
- A bare status update with minimal context: **0.00-0.15**

**Threshold:** 0.35 to pass Layer 1 alone. Below 0.35 → proceed to Layer 2.

### Layer 2: Embedding Classifier

Uses the existing decision embeddings in the vector store. Compares against centroids of known-good decisions vs known noise.

```python
class DecisionClassifier:
    """Embedding-based classifier. Self-improving from reviewed decisions."""
    
    def __init__(self, db):
        self.db = db
        self._centroid_real: list[float] | None = None
        self._centroid_noise: list[float] | None = None
        self._last_computed: datetime | None = None
    
    async def compute_centroids(self) -> None:
        """Recompute from reviewed decisions.
        
        Called periodically (e.g., after Tier 2 review batches).
        Uses review outcomes to separate real decisions from noise.
        """
        # Real decisions: reviewed with outcome in (success, failure, partial)
        real = await self.db.execute("""
            SELECT embedding FROM decisions 
            WHERE review_outcome IN ('success', 'failure', 'partial')
            AND embedding IS NOT NULL
        """)
        
        # Noise: reviewed with outcome = 'not_a_decision' or 'noise'
        # Also include auto-rejected decisions from this gate
        noise = await self.db.execute("""
            SELECT embedding FROM decisions 
            WHERE review_outcome IN ('not_a_decision', 'noise', 'rejected_by_gate')
            AND embedding IS NOT NULL
        """)
        
        if len(real) >= 5:  # Minimum sample
            self._centroid_real = mean_vector(real)
        if len(noise) >= 5:
            self._centroid_noise = mean_vector(noise)
        
        self._last_computed = datetime.now(UTC)
    
    def classify(self, embedding: list[float]) -> tuple[str, float]:
        """Classify an embedding as 'decision' or 'noise'.
        
        Returns (label, confidence).
        If centroids aren't computed, returns ('unknown', 0.5).
        """
        if not self._centroid_real:
            return ("unknown", 0.5)
        
        dist_real = cosine_distance(embedding, self._centroid_real)
        
        if self._centroid_noise:
            dist_noise = cosine_distance(embedding, self._centroid_noise)
            # Confidence = how much closer to one centroid vs the other
            total = dist_real + dist_noise
            if total == 0:
                return ("unknown", 0.5)
            confidence = dist_noise / total  # Higher = more like real decision
            label = "decision" if confidence > 0.5 else "noise"
            return (label, confidence)
        else:
            # No noise centroid yet — use distance from real only
            # Empirical threshold: decisions cluster at cosine < 0.3
            if dist_real < 0.35:
                return ("decision", 0.7)
            elif dist_real > 0.55:
                return ("noise", 0.7)
            else:
                return ("unknown", 0.5)
```

**Bootstrap problem:** We need reviewed decisions to compute centroids. Solutions:
1. **Seed from existing data.** CSTP already has 333+ decisions with 158+ reviewed. Run a one-time label pass: mark known noise (the 16 status updates from this week's review).
2. **Grow organically.** Every Tier 2 review that marks `not_a_decision` feeds the noise centroid. Every `success`/`failure` review feeds the real centroid.
3. **Recompute trigger.** Recompute centroids after every 10 new reviews, or on `cstp.recomputeClassifier` RPC call.

**Cost:** One embedding computation per decision (~$0.00001) + one cosine comparison. Negligible.

### Layer 3: LLM Gate (Tiebreaker)

Only fires when Layers 1 and 2 disagree, or both are in the ambiguous zone.

```python
GATE_PROMPT = """Classify this text as DECISION or STATUS_UPDATE.

A DECISION is:
- A choice between alternatives under uncertainty
- A commitment to a path that could be wrong
- Something with an observable outcome that can be reviewed later

A STATUS_UPDATE is:
- Reporting what happened or what exists
- Confirming completion of work
- Explaining current state or capabilities
- Presenting data or results

Text: "{text}"
Context: "{context}"

Reply with JSON: {{"classification": "DECISION" or "STATUS_UPDATE", "reason": "one sentence"}}"""

async def llm_gate(text: str, context: str) -> tuple[str, str]:
    """Haiku-class LLM tiebreaker. ~$0.0005, ~1-2s."""
    response = await call_haiku(GATE_PROMPT.format(text=text, context=context))
    parsed = json.loads(response)
    return parsed["classification"], parsed["reason"]
```

**When it fires:**
- Layer 1 score is 0.20-0.45 (ambiguous) AND Layer 2 returns "unknown" or confidence < 0.6
- Layer 1 and Layer 2 disagree (one says decision, other says noise)
- Expected trigger rate: ~10-15% of submissions (most are clearly one or the other)

---

## Combined Gate Logic

```python
async def admission_gate(
    decision: dict,
    embedding: list[float] | None,
    tracker_state: dict | None,
    classifier: DecisionClassifier,
    settings: Settings,
) -> GateResult:
    """Three-layer admission gate for decision recording.
    
    Returns GateResult with accept/reject and reasoning.
    """
    if not settings.decision_admission_enabled:
        return GateResult(accepted=True, reason="gate-disabled")
    
    mode = settings.decision_admission_mode  # "shadow" | "warn" | "enforce"
    
    # Layer 1: Structural scoring
    struct_score, struct_weights = structural_score(decision, tracker_state)
    
    # Fast accept: strong structural signal
    if struct_score >= 0.60:
        return GateResult(
            accepted=True,
            reason=f"structural-accept (score={struct_score:.2f})",
            layer="structural",
            scores={"structural": struct_score},
        )
    
    # Fast reject: zero structural signal
    if struct_score <= 0.10:
        return _gate_result(
            accepted=False,
            reason=f"structural-reject: no deliberation trace, no reasoning diversity, "
                   f"no alternatives (score={struct_score:.2f})",
            layer="structural",
            scores={"structural": struct_score},
            mode=mode,
        )
    
    # Layer 2: Embedding classifier
    embed_label, embed_conf = ("unknown", 0.5)
    if embedding and classifier._centroid_real:
        embed_label, embed_conf = classifier.classify(embedding)
    
    # Agreement between layers → decide
    if struct_score >= 0.35 and embed_label == "decision" and embed_conf > 0.6:
        return GateResult(
            accepted=True,
            reason=f"layers-agree-accept (struct={struct_score:.2f}, "
                   f"embed={embed_label}@{embed_conf:.2f})",
            layer="combined",
            scores={"structural": struct_score, "embedding": embed_conf},
        )
    
    if struct_score <= 0.25 and embed_label == "noise" and embed_conf > 0.6:
        return _gate_result(
            accepted=False,
            reason=f"layers-agree-reject (struct={struct_score:.2f}, "
                   f"embed={embed_label}@{embed_conf:.2f})",
            layer="combined",
            scores={"structural": struct_score, "embedding": embed_conf},
            mode=mode,
        )
    
    # Disagreement or ambiguity → Layer 3 tiebreaker
    if settings.decision_admission_llm_enabled:
        llm_label, llm_reason = await llm_gate(
            decision.get("decision", ""),
            decision.get("context", ""),
        )
        accepted = llm_label == "DECISION"
        return _gate_result(
            accepted=accepted,
            reason=f"llm-tiebreaker: {llm_reason} (struct={struct_score:.2f}, "
                   f"embed={embed_label}@{embed_conf:.2f})",
            layer="llm",
            scores={"structural": struct_score, "embedding": embed_conf, "llm": 1.0 if accepted else 0.0},
            mode=mode,
        )
    
    # No LLM available — use structural + embedding average
    avg = (struct_score + (embed_conf if embed_label == "decision" else 1.0 - embed_conf)) / 2
    accepted = avg >= 0.40
    return _gate_result(
        accepted=accepted,
        reason=f"averaged (struct={struct_score:.2f}, embed={embed_label}@{embed_conf:.2f}, avg={avg:.2f})",
        layer="averaged",
        scores={"structural": struct_score, "embedding": embed_conf},
        mode=mode,
    )


def _gate_result(accepted: bool, reason: str, layer: str,
                 scores: dict, mode: str) -> GateResult:
    """Apply mode: shadow logs but accepts, warn accepts with warning, enforce rejects."""
    if mode == "shadow":
        return GateResult(accepted=True, reason=f"shadow-pass ({reason})",
                         layer=layer, scores=scores, shadow_reject=not accepted)
    elif mode == "warn":
        return GateResult(accepted=True, reason=f"warn ({reason})",
                         layer=layer, scores=scores, warning=reason if not accepted else None)
    else:  # enforce
        return GateResult(accepted=accepted, reason=reason, layer=layer, scores=scores)


@dataclass
class GateResult:
    accepted: bool
    reason: str
    layer: str = ""
    scores: dict = field(default_factory=dict)
    shadow_reject: bool = False  # Would have rejected in enforce mode
    warning: str | None = None   # Warning message (warn mode)
```

---

## Integration Points

### CSTP Server: `recordDecision` RPC

```python
# In cstp.recordDecision handler, before persisting:
gate_result = await admission_gate(
    decision=params,
    embedding=computed_embedding,
    tracker_state=tracker.get_state(agent_id),
    classifier=self._decision_classifier,
    settings=self._settings,
)

if not gate_result.accepted:
    return {
        "rejected": True,
        "reason": gate_result.reason,
        "suggestion": "This looks like a status update, not a decision. "
                      "Decisions involve choosing between alternatives under uncertainty. "
                      "If this IS a decision, add deliberation context: "
                      "query similar decisions first, specify alternatives considered, "
                      "and use diverse reasoning types.",
        "scores": gate_result.scores,
    }

# If shadow mode, persist but tag
if gate_result.shadow_reject:
    decision["_gate_shadow_reject"] = True
    decision["_gate_reason"] = gate_result.reason
```

### CSTP Server: New RPC Methods

```python
# Recompute classifier centroids
"cstp.recomputeClassifier" -> None
# Triggered after batch reviews or on schedule

# Get gate stats
"cstp.getGateStats" -> {
    "total_evaluated": int,
    "accepted": int,
    "rejected": int,
    "shadow_rejects": int,
    "llm_tiebreakers": int,
    "centroid_sample_sizes": {"real": int, "noise": int},
    "last_centroid_update": str,
}

# Manual label for classifier training
"cstp.labelDecision" -> None
# params: {"id": str, "label": "decision" | "noise"}
```

### Nous Integration

Nous has CSTP built into its Brain. The gate runs server-side, so Nous gets it automatically through the RPC. No Nous code changes needed for basic gating.

For the structural scoring to work well, Nous needs to ensure:
1. `pre_action` is called before `recordDecision` (creates deliberation trace)
2. Reasons include type diversity (already enforced by F027 quality gate)
3. Alternatives are mentioned in context when they exist

### Review Outcome Labels

Add `not_a_decision` as a valid review outcome alongside `success`, `failure`, `partial`:

```python
VALID_OUTCOMES = {"success", "failure", "partial", "not_a_decision"}
```

Decisions labeled `not_a_decision` in review feed the noise centroid. This closes the feedback loop: bad decisions that slip through the gate get caught in review, improve the classifier, and prevent future noise.

---

## Configuration

```python
# CSTP server settings
decision_admission_enabled: bool = True
decision_admission_mode: str = "shadow"  # "shadow" | "warn" | "enforce"
decision_admission_llm_enabled: bool = False  # Enable Layer 3 tiebreaker
decision_admission_llm_model: str = "claude-haiku-4-5-20251001"
decision_admission_structural_threshold: float = 0.35
decision_admission_centroid_min_samples: int = 5
decision_admission_recompute_after_reviews: int = 10
```

Environment variables: `CSTP_ADMISSION_ENABLED`, `CSTP_ADMISSION_MODE`, etc.

**Rollout plan:**
1. Deploy in `shadow` mode — log what would be rejected, don't block
2. After 1 week, review shadow rejects — verify <10% false positive rate
3. Switch to `warn` mode — accept but return warning to agent
4. After 1 week of clean warns, switch to `enforce`

---

## Cost Model

| Layer | Cost | Latency | Trigger Rate |
|-------|------|---------|-------------|
| Structural scoring | $0 | <1ms | 100% |
| Embedding classifier | ~$0.00001 | ~5ms | ~50% (skipped on fast accept/reject) |
| LLM tiebreaker | ~$0.0005 | ~1-2s | ~10-15% |

**Expected cost per 100 decisions:** ~$0.005-0.008 (effectively free).

---

## Metrics & Monitoring

Track in gate stats:
- **Rejection rate by layer** — which layer catches the most noise?
- **False positive rate** — decisions rejected by gate but later re-submitted and accepted (indicates gate too aggressive)
- **Shadow reject accuracy** — in shadow mode, how often do shadow rejects match reviewer `not_a_decision` labels?
- **Centroid drift** — distance between real/noise centroids over time (should stay stable or grow)
- **LLM agreement with layers 1+2** — does the tiebreaker confirm or overturn?

---

## Bootstrap Procedure

1. **Label existing data.** Run through the 54 decisions from this week's Tier 2 review. Mark 16 as `not_a_decision`. Mark 32 as their actual outcomes. (3 partial already labeled.)
2. **Compute initial centroids.** 32 real + 16 noise = 48 labeled samples. Above the 5-sample minimum.
3. **Deploy in shadow mode.** Gate evaluates but doesn't block.
4. **Run for 1-2 weeks.** Collect shadow reject data.
5. **Validate.** Compare shadow rejects against next Tier 2 review findings.
6. **Promote to enforce.** Once false positive rate < 10%.

---

## Honest Limitations

- **Structural scoring favors agents that use CSTP workflow.** Agents that skip `pre_action` and go straight to `recordDecision` will score lower even for real decisions. This is partly intentional (workflow compliance) but could over-penalize simple use cases.
- **Embedding classifier needs data.** Cold start with <5 labeled samples per class = Layer 2 is disabled. Small deployments may never accumulate enough noise labels.
- **LLM gate can be wrong.** Haiku is cheap but not infallible. Edge cases: "Decided to report the results" (is this a decision about reporting, or a status update?).
- **Sophisticated agents can game it.** An agent that always adds fake alternatives and diverse reasons to its status updates will pass the gate. This isn't a security boundary — it's a hygiene filter for honest but sloppy logging.

---

## Files to Create/Modify

### CSTP Server
- `src/cstp/admission_gate.py` — NEW: AdmissionGate, structural_score, GateResult
- `src/cstp/classifier.py` — NEW: DecisionClassifier, centroid computation
- `src/cstp/server.py` — Hook gate into recordDecision, add new RPCs
- `src/cstp/models.py` — Add GateResult, extend review outcomes
- `src/cstp/config.py` — Add admission gate settings
- `tests/test_admission_gate.py` — NEW: unit tests

### Nous (Brain module)
- No immediate changes needed — gate runs server-side via RPC
- Future: expose gate scores in dashboard health view

---

*"The most productive kinds of thought are not the methods with which we solve particular problems, but those that lead us to formulating useful new kinds of descriptions."* — Minsky (Ch. 14)

*The admission gate doesn't solve decision quality. It solves decision identity — teaching the system what a decision IS, so quality measures apply to the right things.*
