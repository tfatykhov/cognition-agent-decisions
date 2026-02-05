# F014 Implementation Plan: Rolling Calibration Windows

**Spec:** `docs/specs/V0.9.0-FEATURES.md`  
**Skill:** python-pro  

---

## Overview

Add time-windowed calibration metrics to `cstp.getCalibration`:
- 30-day rolling window
- 60-day rolling window
- 90-day rolling window
- All-time (existing, default)

---

## Current State

### Files to Modify
- `a2a/cstp/calibration_service.py` — main logic
- `a2a/cstp/dispatcher.py` — param handling (minimal)
- `dashboard/cstp_client.py` — add window param
- `dashboard/templates/calibration.html` — window selector

### Existing API
```python
GetCalibrationRequest:
    agent: str | None
    category: str | None
    stakes: str | None
    since: str | None      # Already supports date filtering!
    until: str | None      # Already supports date filtering!
    min_decisions: int
    group_by: str | None
    project: str | None
    feature: str | None
```

**Key insight:** `since`/`until` already exist — we just need to add `window` as a convenience that translates to date filters.

---

## Implementation Steps

### Phase 1: Backend (45 min)

#### Step 1.1: Add window param to request (10 min)

**File:** `a2a/cstp/calibration_service.py`

```python
@dataclass
class GetCalibrationRequest:
    # ... existing fields ...
    window: str | None = None  # "30d", "60d", "90d", "all"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GetCalibrationRequest":
        filters = data.get("filters", {})
        return cls(
            # ... existing ...
            window=data.get("window"),  # Top-level param, not in filters
        )
```

#### Step 1.2: Add window-to-date conversion helper (10 min)

**File:** `a2a/cstp/calibration_service.py`

```python
def window_to_dates(window: str | None) -> tuple[str | None, str | None]:
    """Convert window shorthand to since/until dates.
    
    Args:
        window: "30d", "60d", "90d", or None/all
        
    Returns:
        (since_date, until_date) as ISO date strings
    """
    if not window or window == "all":
        return None, None
    
    now = datetime.now(UTC)
    until_date = now.strftime("%Y-%m-%d")
    
    if window == "30d":
        since = now - timedelta(days=30)
    elif window == "60d":
        since = now - timedelta(days=60)
    elif window == "90d":
        since = now - timedelta(days=90)
    else:
        return None, None  # Unknown window, ignore
    
    since_date = since.strftime("%Y-%m-%d")
    return since_date, until_date
```

#### Step 1.3: Apply window in get_calibration (10 min)

**File:** `a2a/cstp/calibration_service.py`

```python
async def get_calibration(
    request: GetCalibrationRequest,
    decisions_path: str | None = None,
) -> GetCalibrationResponse:
    # Convert window to date filters
    window_since, window_until = window_to_dates(request.window)
    
    # Window overrides explicit since/until if set
    effective_since = window_since or request.since
    effective_until = window_until or request.until
    
    decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        agent=request.agent,
        category=request.category,
        stakes=request.stakes,
        since=effective_since,
        until=effective_until,
        project=request.project,
        feature=request.feature,
    )
    # ... rest unchanged ...
```

#### Step 1.4: Add period metadata to response (15 min)

**File:** `a2a/cstp/calibration_service.py`

```python
@dataclass
class CalibrationResult:
    # ... existing fields ...
    window: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            # ... existing ...
        }
        if self.window:
            result["window"] = self.window
        if self.period_start:
            result["periodStart"] = self.period_start
        if self.period_end:
            result["periodEnd"] = self.period_end
        return result
```

Update `calculate_calibration` to accept and pass through window info.

---

### Phase 2: Dashboard (30 min)

#### Step 2.1: Update CSTP client (10 min)

**File:** `dashboard/cstp_client.py`

```python
async def get_calibration(
    self,
    project: str | None = None,
    category: str | None = None,
    window: str | None = None,  # NEW
) -> CalibrationStats:
    params: dict[str, Any] = {}
    if project:
        params["project"] = project
    if category:
        params["category"] = category
    if window:
        params["window"] = window
    
    result = await self._call("cstp.getCalibration", params)
    return CalibrationStats.from_dict(result)
```

#### Step 2.2: Update calibration route (10 min)

**File:** `dashboard/app.py`

```python
@app.route("/calibration")
@auth
def calibration() -> str:
    project = request.args.get("project") or None
    window = request.args.get("window") or None  # NEW
    
    try:
        stats = run_async(cstp.get_calibration(
            project=project,
            window=window,  # NEW
        ))
    except CSTPError as e:
        flash(f"Error loading calibration: {e}", "error")
        stats = None
    
    return render_template(
        "calibration.html",
        stats=stats,
        project=project,
        window=window,  # NEW
    )
```

#### Step 2.3: Add window selector to template (10 min)

**File:** `dashboard/templates/calibration.html`

```html
<form method="get" class="grid">
    <select name="window" aria-label="Time window">
        <option value="">All Time</option>
        <option value="30d" {% if window == '30d' %}selected{% endif %}>Last 30 Days</option>
        <option value="60d" {% if window == '60d' %}selected{% endif %}>Last 60 Days</option>
        <option value="90d" {% if window == '90d' %}selected{% endif %}>Last 90 Days</option>
    </select>
    <button type="submit">Apply</button>
</form>
```

---

### Phase 3: Tests (20 min)

#### Step 3.1: Unit tests for window conversion (10 min)

**File:** `a2a/cstp/tests/test_calibration.py`

```python
def test_window_to_dates_30d():
    since, until = window_to_dates("30d")
    assert since is not None
    assert until is not None
    # since should be 30 days before until

def test_window_to_dates_all():
    since, until = window_to_dates("all")
    assert since is None
    assert until is None

def test_window_to_dates_none():
    since, until = window_to_dates(None)
    assert since is None
    assert until is None
```

#### Step 3.2: Integration test (10 min)

Test that calibration with window actually filters decisions.

---

## Checklist

| # | Task | Est. | Status |
|---|------|------|--------|
| 1 | Add `window` to GetCalibrationRequest | 10m | ⬜ |
| 2 | Add `window_to_dates()` helper | 10m | ⬜ |
| 3 | Apply window in `get_calibration()` | 10m | ⬜ |
| 4 | Add period metadata to CalibrationResult | 15m | ⬜ |
| 5 | Update dashboard CSTP client | 10m | ⬜ |
| 6 | Update calibration route | 10m | ⬜ |
| 7 | Add window selector to template | 10m | ⬜ |
| 8 | Add unit tests | 10m | ⬜ |
| 9 | Add integration test | 10m | ⬜ |
| 10 | Create PR + code review | 15m | ⬜ |

**Total:** ~2 hours

---

## API Example

**Request:**
```json
{
    "jsonrpc": "2.0",
    "method": "cstp.getCalibration",
    "params": {
        "window": "30d",
        "filters": {
            "category": "architecture"
        }
    },
    "id": 1
}
```

**Response:**
```json
{
    "overall": {
        "brierScore": 0.05,
        "accuracy": 0.91,
        "totalDecisions": 15,
        "reviewedDecisions": 12,
        "calibrationGap": -0.02,
        "interpretation": "well_calibrated",
        "window": "30d",
        "periodStart": "2026-01-06",
        "periodEnd": "2026-02-05"
    },
    "byConfidenceBucket": [...],
    "recommendations": [...]
}
```
