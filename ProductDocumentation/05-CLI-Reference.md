# CLI Reference

The `cognition` CLI provides direct access to all core engine capabilities without requiring the HTTP server.

**Location:** `bin/cognition`

---

## Prerequisites

The CLI requires:

- Python 3.11+
- `cognition-engines` package installed (see [Installation Guide](06-Installation-Guide.md))
- `GEMINI_API_KEY` environment variable set (for embedding operations)
- ChromaDB accessible at `CHROMA_URL` (default: `http://localhost:8000`)

---

## Commands

### `cognition index <directory>`

Index all YAML decision files from a directory into ChromaDB.

```bash
# Index decisions from the default directory
python bin/cognition index decisions/

# Index from a custom directory
python bin/cognition index /path/to/my/decisions/
```

**Behavior:**

1. Recursively finds all `.yaml` and `.yml` files
2. Parses each file, looking for `decision` or `title` keys
3. Generates embeddings via Gemini API
4. Upserts into the ChromaDB `cognition_decisions` collection
5. Reports count of files found, parsed, and indexed

---

### `cognition query <context>`

Search for semantically similar decisions.

```bash
# Basic query
python bin/cognition query "database selection for state storage"

# Filter by category
python bin/cognition query "auth approach" --category security

# Filter by minimum confidence
python bin/cognition query "deployment strategy" --min-confidence 0.7
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--category CAT` | string | Filter by decision category |
| `--min-confidence N` | float | Minimum confidence threshold |

**Output:**

```
============================================================
Query: database selection for state storage
============================================================

[1] Use ChromaDB for semantic memory
    Category: architecture
    Confidence: 0.85
    Distance: 0.2340
    Status: reviewed

[2] Switch to PostgreSQL for persistence
    Category: infrastructure
    Confidence: 0.72
    Distance: 0.4120
    Status: pending
```

---

### `cognition check`

Evaluate guardrails against a decision context.

```bash
# Check a high-stakes architecture decision
python bin/cognition check --category architecture --stakes high --confidence 0.8

# Check production deployment
python bin/cognition check --affects-production true --code-review-completed false

# Trading decision
python bin/cognition check --category trading --decision-type strategy_change --backtest-completed true
```

**Options:** Any `--key value` pair becomes a context field. Underscores in keys are replaced from hyphens.

**Output:**

```
Loaded 3 guardrails

============================================================
Context: {
  "category": "architecture",
  "stakes": "high",
  "confidence": 0.8
}
============================================================

✅ ALLOWED - All guardrails passed

  ✅ no-production-without-review: Not applicable
  ✅ no-high-stakes-low-confidence: Confidence 0.8 meets minimum
  ✅ no-trading-strategy-without-backtest: Not applicable
```

**Exit codes:** `0` = allowed, `1` = blocked

---

### `cognition guardrails`

List all loaded guardrail definitions.

```bash
python bin/cognition guardrails
```

**Output:**

```
Loaded 3 guardrails:

🚫 no-production-without-review
   Production changes require code review

🚫 no-high-stakes-low-confidence
   High-stakes decisions need minimum confidence

🚫 no-trading-strategy-without-backtest
   Trading strategy changes need backtesting
   Scope: CryptoTrader
```

---

### `cognition count`

Count the number of indexed decisions in ChromaDB.

```bash
python bin/cognition count
```

**Output:**

```
Indexed decisions: 47
```

---

### `cognition patterns <subcommand>`

Run pattern analysis on decision history.

#### `cognition patterns calibration`

Confidence calibration report with Brier scores.

```bash
# Text output
python bin/cognition patterns calibration --dir decisions/

# JSON output
python bin/cognition patterns calibration --dir decisions/ --format json
```

**Output:**

```
============================================================
Confidence Calibration Report
============================================================

Total decisions: 47
With outcomes: 32
Overall Brier: 0.1423
Interpretation: Good calibration

Bucket       Count    Predicted  Actual     Brier
--------------------------------------------------
0.0-0.2      2        0.15       0.00       0.0225
0.2-0.4      5        0.32       0.40       0.0512
0.4-0.6      8        0.52       0.50       0.0984
0.6-0.8      10       0.72       0.70       0.0892
0.8-1.0      7        0.88       0.86       0.0210
```

#### `cognition patterns categories`

Category success analysis.

```bash
python bin/cognition patterns categories --dir decisions/
```

#### `cognition patterns antipatterns`

Detect decision anti-patterns.

```bash
python bin/cognition patterns antipatterns --dir decisions/
```

**Detected anti-patterns:**

- **Overcalibration** — Confidence always in a narrow band
- **Flip-flopping** — Contradictory decisions in short timeframes
- **Anchoring** — Over-reliance on first option considered
- **Blind spots** — Categories with zero reviewed outcomes
- **Hot-hand fallacy** — Overconfidence after a success streak

#### `cognition patterns full`

Complete pattern report (best used with `--format json`).

```bash
python bin/cognition patterns full --dir decisions/ --format json > report.json
```

**Common options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--dir DIR` | `-d` | `decisions/` | Path to decisions directory |
| `--format FMT` | `-f` | `text` | Output format: `text` or `json` |
