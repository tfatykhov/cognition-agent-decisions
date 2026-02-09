# CLI Reference

Cognition Engines provides two CLI tools:
1. **`bin/cognition`** — Local/offline tool for direct database access (server-side)
2. **`scripts/cstp.py`** — Remote client for connecting to the CSTP server (client-side)

---

## 1. Local CLI (`bin/cognition`)

**Location:** `bin/cognition`
**Use case:** Server maintenance, offline indexing, direct guardrail checks.

### Prerequisites

- Python 3.11+
- `cognition-engines` package installed
- `GEMINI_API_KEY` environment variable
- ChromaDB accessible

### Commands

#### `cognition index <directory>`

Index all YAML decision files from a directory into ChromaDB.

```bash
# Index decisions from the default directory
python bin/cognition index decisions/
```

#### `cognition query <context>`

Search for semantically similar decisions.

```bash
# Basic query
python bin/cognition query "database selection"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--category CAT` | Filter by decision category |
| `--min-confidence N` | Minimum confidence threshold |

#### `cognition check`

Evaluate guardrails against a decision context.

```bash
python bin/cognition check --category architecture --stakes high --confidence 0.8
```

#### `cognition guardrails`

List all loaded guardrail definitions.

#### `cognition count`

Count indexed decisions.

#### `cognition patterns <subcommand>`

Run pattern analysis: `calibration`, `categories`, `antipatterns`, `full`.

---

## 2. CSTP Client (`scripts/cstp.py`)

**Location:** `scripts/cstp.py`
**Use case:** Agent interaction, recording decisions, querying the server.

### Setup

Requires `.secrets/cstp.env` with `CSTP_URL` and `CSTP_TOKEN`.

### `cstp.py query`

Query similar decisions from the server.

```bash
python scripts/cstp.py query "how to persist state" --top 5 --mode hybrid
```

**Options:**

| Flag | Description |
|------|-------------|
| `--top N` | Number of results (default: 5) |
| `--category CAT` | Filter by category |
| `--project PROJ` | Filter by project |
| `--mode MODE` | Retrieval mode: `semantic`, `keyword`, `hybrid` |
| `--bridge-side SIDE` | Search by bridge side: `structure`, `function` |

### `cstp.py check`

Check guardrails before acting.

```bash
python scripts/cstp.py check -d "deploy to prod" -s high -f 0.9
```

### `cstp.py record`

Record a decision. Record early to capture deliberation inputs.

```bash
python scripts/cstp.py record \
  -d "Plan: Use PostgreSQL for persistence" \
  -c architecture \
  -s high \
  -f 0.85 \
  --tag database --tag infrastructure \
  --pattern "Choose ACID-compliant stores for transactional data"
```

**Options:**

| Flag | Description |
|------|-------------|
| `-d`, `--decision` | Decision text (required) |
| `-c`, `--category` | Category (required) |
| `-s`, `--stakes` | Stakes: low, medium, high, critical |
| `-f`, `--confidence` | Confidence (0.0-1.0) |
| `--context` | Context description |
| `-r`, `--reason` | Add reason (type:text, repeatable) |
| `--tag`, `-t` | Reusable keyword tag (repeatable) |
| `--pattern` | Abstract pattern this decision represents |
| `--project` | Project (owner/repo) |
| `--pr` | PR number |
| `--structure` | Bridge: structure/pattern |
| `--function` | Bridge: function/purpose |
| `--tolerance` | Bridge: features that don't matter |
| `--enforcement` | Bridge: features that must be present |
| `--prevention` | Bridge: features that must be absent |

### `cstp.py think`

Record a chain-of-thought reasoning step. Pre-decision mode (no `--id`) accumulates in the tracker; post-decision mode (`--id`) appends to an existing decision's trace.

```bash
# Pre-decision: captured automatically when you record
python scripts/cstp.py think "Considering Redis vs Memcached for caching"

# Post-decision: appends to existing decision trace
python scripts/cstp.py think --id <ID> "Redis chosen because it supports persistence"
```

### `cstp.py update`

Update an existing decision's fields. Use after recording to finalize with actual outcomes.

```bash
python scripts/cstp.py update <ID> \
  -d "Used PostgreSQL with connection pooling" \
  --context "Deployed with PgBouncer. 3 replicas." \
  --tag database --tag infrastructure --tag pgbouncer
```

**Options:**

| Flag | Description |
|------|-------------|
| `-d`, `--decision` | Updated decision text |
| `-f`, `--confidence` | Updated confidence (0.0-1.0) |
| `--context` | Updated context |
| `--tag`, `-t` | Tags (repeatable, replaces existing) |
| `--pattern` | Abstract pattern |

### `cstp.py pre`

Pre-decision helper: runs query + guardrail check in one call. Use before recording.

```bash
python scripts/cstp.py pre "deploy retry logic to production" -s high -f 0.85
```

### `cstp.py get`

Get full decision details by ID, including reasons, bridge, related decisions, and deliberation.

```bash
python scripts/cstp.py get <ID>
```

### `cstp.py review`

Review a decision outcome.

```bash
python scripts/cstp.py review --id <ID> --outcome success
```

### `cstp.py calibration`

Get calibration stats.

```bash
python scripts/cstp.py calibration
```

### `cstp.py reason-stats`

Get reason-type statistics.

```bash
python scripts/cstp.py reason-stats --min-reviewed 5
```
