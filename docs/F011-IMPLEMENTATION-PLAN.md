# F011 Implementation Plan: Web Dashboard (Detailed)

**Spec:** `docs/specs/F011-WEB-DASHBOARD.md`  
**Skill:** python-pro (type-safe Python 3.11+)  
**Decision IDs:** cd235c3e, 8bcce9f4  

---

## 1. Docker Container Setup

### 1.1 Directory Structure

```
cognition-agent-decisions/
├── dashboard/
│   ├── Dockerfile
│   ├── docker-compose.yml        # Standalone compose for dashboard
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app.py                    # Flask entry point
│   ├── config.py                 # Environment config dataclass
│   ├── cstp_client.py            # CSTP API wrapper
│   ├── models.py                 # Dataclasses for Decision, Calibration
│   ├── auth.py                   # Basic auth decorator
│   ├── templates/
│   │   ├── base.html             # Layout with nav
│   │   ├── login.html            # Login page (optional)
│   │   ├── decisions.html        # Decision list
│   │   ├── decision.html         # Decision detail
│   │   ├── review.html           # Outcome review form
│   │   └── calibration.html      # Calibration dashboard
│   ├── static/
│   │   └── style.css             # Custom CSS overrides
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py           # pytest fixtures
│       ├── test_app.py           # Route tests
│       └── test_cstp_client.py   # Client tests
```

### 1.2 Dockerfile

```dockerfile
# dashboard/Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 dashboard && chown -R dashboard:dashboard /app
USER dashboard

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--access-logfile", "-", "app:app"]
```

### 1.3 docker-compose.yml (Dashboard Standalone)

```yaml
# dashboard/docker-compose.yml
version: '3.8'

services:
  dashboard:
    build: .
    container_name: cstp-dashboard
    ports:
      - "8080:8080"
    environment:
      - CSTP_URL=${CSTP_URL:-http://host.docker.internal:9991}
      - CSTP_TOKEN=${CSTP_TOKEN}
      - DASHBOARD_USER=${DASHBOARD_USER:-admin}
      - DASHBOARD_PASS=${DASHBOARD_PASS}
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - cstp-network

networks:
  cstp-network:
    external: true
```

### 1.4 Integration with Main docker-compose.yml

```yaml
# Add to main cognition-agent-decisions/docker-compose.yml
  dashboard:
    build: ./dashboard
    container_name: cstp-dashboard
    ports:
      - "8080:8080"
    environment:
      - CSTP_URL=http://cstp-server:9991
      - CSTP_TOKEN=${CSTP_TOKEN}
      - DASHBOARD_USER=${DASHBOARD_USER:-admin}
      - DASHBOARD_PASS=${DASHBOARD_PASS}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      cstp-server:
        condition: service_healthy
    restart: unless-stopped
```

### 1.5 requirements.txt

```txt
flask>=3.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
gunicorn>=21.0.0
```

### 1.6 pyproject.toml

```toml
[project]
name = "cstp-dashboard"
version = "0.1.0"
description = "Web dashboard for CSTP decision intelligence"
requires-python = ">=3.11"
dependencies = [
    "flask>=3.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "gunicorn>=21.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=. --cov-report=term-missing"
```

---

## 2. Detailed Implementation Steps

### Step 1: Create Directory Structure (5 min)

```bash
cd cognition-agent-decisions
mkdir -p dashboard/{templates,static,tests}
touch dashboard/__init__.py
touch dashboard/{app,config,cstp_client,models,auth}.py
touch dashboard/templates/{base,decisions,decision,review,calibration}.html
touch dashboard/static/style.css
touch dashboard/tests/{__init__,conftest,test_app,test_cstp_client}.py
touch dashboard/{Dockerfile,docker-compose.yml,requirements.txt,pyproject.toml}
```

### Step 2: config.py (10 min)

```python
"""Configuration from environment variables."""
from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class Config:
    """Dashboard configuration loaded from environment."""
    
    cstp_url: str = environ.get("CSTP_URL", "http://localhost:9991")
    cstp_token: str = environ.get("CSTP_TOKEN", "")
    dashboard_user: str = environ.get("DASHBOARD_USER", "admin")
    dashboard_pass: str = environ.get("DASHBOARD_PASS", "")
    dashboard_port: int = int(environ.get("DASHBOARD_PORT", "8080"))
    secret_key: str = environ.get("SECRET_KEY", "dev-secret-change-me")
    
    def validate(self) -> list[str]:
        """Validate required config. Returns list of errors."""
        errors = []
        if not self.cstp_token:
            errors.append("CSTP_TOKEN is required")
        if not self.dashboard_pass:
            errors.append("DASHBOARD_PASS is required")
        return errors


config = Config()
```

### Step 3: models.py (15 min)

```python
"""Data models for CSTP dashboard."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Reason:
    """A reason supporting a decision."""
    type: str
    text: str
    strength: float = 0.8


@dataclass
class ProjectContext:
    """Project context for a decision."""
    project: str | None = None
    feature: str | None = None
    pr: int | None = None
    file: str | None = None
    line: int | None = None
    commit: str | None = None


@dataclass
class Decision:
    """A decision record."""
    id: str
    summary: str
    category: str
    stakes: str
    confidence: float
    created_at: datetime
    context: str | None = None
    reasons: list[Reason] = field(default_factory=list)
    outcome: str | None = None
    actual_result: str | None = None
    lessons: str | None = None
    reviewed_at: datetime | None = None
    project_context: ProjectContext | None = None
    agent_id: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Create from API response dict."""
        reasons = [
            Reason(**r) if isinstance(r, dict) else r
            for r in data.get("reasons", [])
        ]
        
        project_context = None
        if pc := data.get("project_context"):
            project_context = ProjectContext(**pc)
        
        return cls(
            id=data["id"],
            summary=data.get("summary", data.get("decision", "")),
            category=data.get("category", ""),
            stakes=data.get("stakes", "medium"),
            confidence=float(data.get("confidence", 0.5)),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            context=data.get("context"),
            reasons=reasons,
            outcome=data.get("outcome"),
            actual_result=data.get("actual_result"),
            lessons=data.get("lessons"),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"].replace("Z", "+00:00")) if data.get("reviewed_at") else None,
            project_context=project_context,
            agent_id=data.get("agent_id"),
        )
    
    @property
    def outcome_icon(self) -> str:
        """Return emoji icon for outcome status."""
        if not self.outcome:
            return "⏳"
        return {"success": "✅", "partial": "⚠️", "failure": "❌", "abandoned": "🚫"}.get(self.outcome, "❓")


@dataclass
class CategoryStats:
    """Calibration stats for a category."""
    category: str
    total: int
    reviewed: int
    accuracy: float
    brier_score: float


@dataclass
class CalibrationStats:
    """Overall calibration statistics."""
    total_decisions: int
    reviewed_decisions: int
    brier_score: float
    accuracy: float
    interpretation: str
    by_category: list[CategoryStats] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationStats":
        """Create from API response."""
        overall = data.get("overall", {})
        by_cat = [
            CategoryStats(
                category=c["category"],
                total=c["total_decisions"],
                reviewed=c["reviewed_decisions"],
                accuracy=c["accuracy"],
                brier_score=c["brier_score"],
            )
            for c in data.get("by_category", [])
        ]
        recs = [r["message"] for r in data.get("recommendations", [])]
        
        return cls(
            total_decisions=overall.get("total_decisions", 0),
            reviewed_decisions=overall.get("reviewed_decisions", 0),
            brier_score=overall.get("brier_score", 0.0),
            accuracy=overall.get("accuracy", 0.0),
            interpretation=overall.get("interpretation", "unknown"),
            by_category=by_cat,
            recommendations=recs,
        )
```

### Step 4: cstp_client.py (30 min)

```python
"""Async client for CSTP JSON-RPC API."""
import httpx
from typing import Any

from models import Decision, CalibrationStats


class CSTPError(Exception):
    """CSTP API error."""
    pass


class CSTPClient:
    """Async client for CSTP server."""
    
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._request_id = 0
    
    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make JSON-RPC call to CSTP server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/cstp",
                headers=self.headers,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": self._next_id(),
                },
            )
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise CSTPError(data["error"].get("message", "Unknown error"))
            
            return data.get("result", {})
    
    async def list_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        has_outcome: bool | None = None,
        project: str | None = None,
    ) -> tuple[list[Decision], int]:
        """List decisions with optional filters.
        
        Returns (decisions, total_count).
        """
        # Use queryDecisions with empty query for listing
        params: dict[str, Any] = {
            "query": "",
            "top_k": limit,
        }
        if category:
            params["category"] = category
        if has_outcome is not None:
            params["hasOutcome"] = has_outcome
        if project:
            params["project"] = project
        
        result = await self._call("cstp.queryDecisions", params)
        
        decisions = [Decision.from_dict(d) for d in result.get("decisions", [])]
        total = result.get("total", len(decisions))
        
        return decisions, total
    
    async def get_decision(self, decision_id: str) -> Decision | None:
        """Get single decision by ID."""
        # Query with ID as text (will match by ID prefix in results)
        result = await self._call("cstp.queryDecisions", {
            "query": decision_id,
            "top_k": 10,
        })
        
        for d in result.get("decisions", []):
            if d["id"].startswith(decision_id):
                return Decision.from_dict(d)
        
        return None
    
    async def review_decision(
        self,
        decision_id: str,
        outcome: str,
        actual_result: str,
        lessons: str | None = None,
    ) -> bool:
        """Submit outcome review for a decision."""
        params: dict[str, Any] = {
            "id": decision_id,
            "outcome": outcome,
            "actual_result": actual_result,
        }
        if lessons:
            params["lessons"] = lessons
        
        result = await self._call("cstp.reviewDecision", params)
        return result.get("status") == "reviewed"
    
    async def get_calibration(
        self,
        project: str | None = None,
        category: str | None = None,
    ) -> CalibrationStats:
        """Get calibration statistics."""
        params: dict[str, Any] = {}
        if project:
            params["project"] = project
        if category:
            params["category"] = category
        
        result = await self._call("cstp.getCalibration", params)
        return CalibrationStats.from_dict(result)
    
    async def health_check(self) -> bool:
        """Check if CSTP server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers={"Authorization": f"Bearer {self.headers['Authorization'].split()[-1]}"},
                )
                return response.status_code == 200
        except Exception:
            return False
```

### Step 5: auth.py (10 min)

```python
"""Basic authentication for Flask routes."""
from functools import wraps
from typing import Callable, Any

from flask import request, Response

from config import Config


def check_auth(username: str, password: str, config: Config) -> bool:
    """Validate credentials against config."""
    return (
        username == config.dashboard_user
        and password == config.dashboard_pass
    )


def requires_auth(config: Config) -> Callable:
    """Decorator factory for Basic Auth protection."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, config):
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": 'Basic realm="CSTP Dashboard"'},
                )
            return f(*args, **kwargs)
        return decorated
    return decorator
```

### Step 6: app.py (45 min)

```python
"""CSTP Dashboard Flask application."""
import asyncio
from flask import Flask, render_template, request, redirect, url_for, flash, Response

from config import config
from cstp_client import CSTPClient, CSTPError
from auth import requires_auth

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Initialize CSTP client
cstp = CSTPClient(config.cstp_url, config.cstp_token)

# Auth decorator
auth = requires_auth(config)


def run_async(coro):
    """Run async coroutine in sync Flask context."""
    return asyncio.run(coro)


@app.route("/health")
def health() -> Response:
    """Health check endpoint (no auth required)."""
    healthy = run_async(cstp.health_check())
    if healthy:
        return Response("OK", status=200)
    return Response("CSTP unavailable", status=503)


@app.route("/")
@auth
def index():
    """Redirect to decisions list."""
    return redirect(url_for("decisions"))


@app.route("/decisions")
@auth
def decisions():
    """List all decisions with pagination and filters."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    
    has_outcome = None
    if status == "pending":
        has_outcome = False
    elif status == "reviewed":
        has_outcome = True
    
    try:
        decision_list, total = run_async(cstp.list_decisions(
            limit=per_page,
            offset=(page - 1) * per_page,
            category=category,
            has_outcome=has_outcome,
        ))
    except CSTPError as e:
        flash(f"Error loading decisions: {e}", "error")
        decision_list, total = [], 0
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "decisions.html",
        decisions=decision_list,
        page=page,
        total_pages=total_pages,
        total=total,
        category=category,
        status=status,
    )


@app.route("/decisions/<decision_id>")
@auth
def decision_detail(decision_id: str):
    """View single decision."""
    try:
        decision = run_async(cstp.get_decision(decision_id))
        if not decision:
            flash("Decision not found", "error")
            return redirect(url_for("decisions"))
    except CSTPError as e:
        flash(f"Error loading decision: {e}", "error")
        return redirect(url_for("decisions"))
    
    return render_template("decision.html", decision=decision)


@app.route("/decisions/<decision_id>/review", methods=["GET", "POST"])
@auth
def review(decision_id: str):
    """Review decision outcome."""
    try:
        decision = run_async(cstp.get_decision(decision_id))
        if not decision:
            flash("Decision not found", "error")
            return redirect(url_for("decisions"))
    except CSTPError as e:
        flash(f"Error loading decision: {e}", "error")
        return redirect(url_for("decisions"))
    
    if request.method == "POST":
        outcome = request.form.get("outcome", "")
        actual_result = request.form.get("actual_result", "")
        lessons = request.form.get("lessons") or None
        
        if not outcome:
            flash("Outcome is required", "error")
        elif not actual_result:
            flash("Result description is required", "error")
        else:
            try:
                success = run_async(cstp.review_decision(
                    decision_id,
                    outcome,
                    actual_result,
                    lessons,
                ))
                if success:
                    flash("Outcome recorded successfully!", "success")
                    return redirect(url_for("decision_detail", decision_id=decision_id))
                else:
                    flash("Failed to record outcome", "error")
            except CSTPError as e:
                flash(f"Error: {e}", "error")
    
    return render_template("review.html", decision=decision)


@app.route("/calibration")
@auth
def calibration():
    """Calibration dashboard."""
    project = request.args.get("project") or None
    
    try:
        stats = run_async(cstp.get_calibration(project=project))
    except CSTPError as e:
        flash(f"Error loading calibration: {e}", "error")
        stats = None
    
    return render_template("calibration.html", stats=stats, project=project)


if __name__ == "__main__":
    # Validate config on startup
    errors = config.validate()
    if errors:
        print(f"Configuration errors: {errors}")
        exit(1)
    
    app.run(host="0.0.0.0", port=config.dashboard_port, debug=True)
```

---

## 3. Page Mockups (ASCII)

### 3.1 Decision List Page (`/decisions`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🧠 CSTP Dashboard                                   [Decisions] [Calibration]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Decisions (43 total)                                                        │
│  ════════════════════                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Filter:  [All Categories ▼]   [All Status ▼]   [🔍 Apply]              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌────────┬────────────────────────────────────────┬──────────┬──────┬────┐ │
│  │ ID     │ Decision                               │ Category │ Conf │ 📊 │ │
│  ├────────┼────────────────────────────────────────┼──────────┼──────┼────┤ │
│  │ 8bcce9 │ Expand F011 implementation plan with   │ process  │ 90%  │ ⏳ │ │
│  │        │ Docker container details...            │          │      │    │ │
│  ├────────┼────────────────────────────────────────┼──────────┼──────┼────┤ │
│  │ 904cb4 │ Update sub-agent spawn instructions    │ process  │ 90%  │ ⏳ │ │
│  │        │ to include full CSTP...                │          │      │    │ │
│  ├────────┼────────────────────────────────────────┼──────────┼──────┼────┤ │
│  │ 467c59 │ Create web dashboard for CSTP as       │ arch     │ 85%  │ ⏳ │ │
│  │        │ separate Docker service...             │          │      │    │ │
│  ├────────┼────────────────────────────────────────┼──────────┼──────┼────┤ │
│  │ 85e97b │ Configure sub-agents to use CSTP       │ integr   │ 85%  │ ⏳ │ │
│  │        │ with dedicated API keys...             │          │      │    │ │
│  ├────────┼────────────────────────────────────────┼──────────┼──────┼────┤ │
│  │ 88c1c7 │ Keep CSTP in TOOLS.md rather than      │ process  │ 85%  │ ✅ │ │
│  │        │ creating separate skill...             │          │      │    │ │
│  └────────┴────────────────────────────────────────┴──────────┴──────┴────┘ │
│                                                                              │
│  ◀ Previous   Page 1 of 3   Next ▶                                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Decision Detail Page (`/decisions/<id>`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🧠 CSTP Dashboard                                   [Decisions] [Calibration]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ◀ Back to list                                                              │
│                                                                              │
│  Decision: 467c593e                                              ⏳ Pending  │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Create web dashboard for CSTP as separate Docker service with basic    ││
│  │ auth, decision viewing, and outcome review                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌──────────────────┬──────────────────────────────────────────────────────┐│
│  │ Category         │ architecture                                         ││
│  ├──────────────────┼──────────────────────────────────────────────────────┤│
│  │ Stakes           │ medium                                               ││
│  ├──────────────────┼──────────────────────────────────────────────────────┤│
│  │ Confidence       │ 85%                                                  ││
│  ├──────────────────┼──────────────────────────────────────────────────────┤│
│  │ Created          │ 2026-02-05 19:18:00 UTC                              ││
│  ├──────────────────┼──────────────────────────────────────────────────────┤│
│  │ Agent            │ emerson                                              ││
│  └──────────────────┴──────────────────────────────────────────────────────┘│
│                                                                              │
│  Context                                                                     │
│  ───────                                                                     │
│  Tim requested web dashboard for CSTP. Need to plan before implementing.    │
│                                                                              │
│  Reasons                                                                     │
│  ───────                                                                     │
│  • [authority] Tim requested this feature                                    │
│  • [analysis] python-pro skill provides patterns for type-safe Flask apps   │
│                                                                              │
│  Project Context                                                             │
│  ───────────────                                                             │
│  • Project: tfatykhov/cognition-agent-decisions                              │
│  • PR: #16                                                                   │
│                                                                              │
│                              ┌─────────────────┐                             │
│                              │  Review Outcome │                             │
│                              └─────────────────┘                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Outcome Review Page (`/decisions/<id>/review`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🧠 CSTP Dashboard                                   [Decisions] [Calibration]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ◀ Back to decision                                                          │
│                                                                              │
│  Review Outcome: 467c593e                                                    │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  Decision:                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Create web dashboard for CSTP as separate Docker service with basic    ││
│  │ auth, decision viewing, and outcome review                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  Original confidence: 85%                                                    │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  Outcome *                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  ○ Success   - Decision worked as expected                              ││
│  │  ○ Partial   - Partially worked, some adjustments needed                ││
│  │  ○ Failure   - Did not work, had to change approach                     ││
│  │  ○ Abandoned - Never implemented or tested                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  What actually happened? *                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                                                                         ││
│  │ Dashboard deployed successfully. Flask + Pico.css worked well.          ││
│  │ Basic auth is functional. All routes protected.                         ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  Lessons learned (optional)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                                                                         ││
│  │ Pico.css eliminated the need for custom CSS. No build step was key.     ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│              ┌──────────┐                    ┌───────────────┐               │
│              │  Cancel  │                    │ Submit Review │               │
│              └──────────┘                    └───────────────┘               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Calibration Dashboard (`/calibration`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🧠 CSTP Dashboard                                   [Decisions] [Calibration]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Calibration Dashboard                                                       │
│  ═════════════════════                                                       │
│                                                                              │
│  Filter: [All Projects ▼] [Apply]                                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                           OVERALL STATS                                 ││
│  ├─────────────────────────────────────────────────────────────────────────┤│
│  │                                                                         ││
│  │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐              ││
│  │   │ Total         │  │ Reviewed      │  │ Pending       │              ││
│  │   │     43        │  │     28        │  │     15        │              ││
│  │   └───────────────┘  └───────────────┘  └───────────────┘              ││
│  │                                                                         ││
│  │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐              ││
│  │   │ Accuracy      │  │ Brier Score   │  │ Calibration   │              ││
│  │   │    91.3%      │  │     0.04      │  │  ✅ Good      │              ││
│  │   └───────────────┘  └───────────────┘  └───────────────┘              ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  By Category                                                                 │
│  ┌──────────────┬─────────┬──────────┬──────────┬──────────────────────────┐│
│  │ Category     │ Total   │ Reviewed │ Accuracy │ Brier                    ││
│  ├──────────────┼─────────┼──────────┼──────────┼──────────────────────────┤│
│  │ architecture │ 12      │ 10       │ 92%      │ 0.03                     ││
│  │ process      │ 18      │ 12       │ 89%      │ 0.05                     ││
│  │ integration  │ 8       │ 4        │ 100%     │ 0.00                     ││
│  │ tooling      │ 3       │ 2        │ 67%      │ 0.12                     ││
│  │ security     │ 2       │ 0        │ --       │ --                       ││
│  └──────────────┴─────────┴──────────┴──────────┴──────────────────────────┘│
│                                                                              │
│  Recommendations                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 💡 Review more 'tooling' decisions - calibration data is sparse        ││
│  │ 💡 Your 'architecture' predictions are well-calibrated                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Checklist

| # | Task | Est. | Status |
|---|------|------|--------|
| 1 | Create directory structure | 5m | ⬜ |
| 2 | Write `requirements.txt` + `pyproject.toml` | 5m | ⬜ |
| 3 | Write `config.py` | 10m | ⬜ |
| 4 | Write `models.py` | 15m | ⬜ |
| 5 | Write `cstp_client.py` | 30m | ⬜ |
| 6 | Write `auth.py` | 10m | ⬜ |
| 7 | Write `app.py` (routes) | 45m | ⬜ |
| 8 | Write `templates/base.html` | 15m | ⬜ |
| 9 | Write `templates/decisions.html` | 20m | ⬜ |
| 10 | Write `templates/decision.html` | 15m | ⬜ |
| 11 | Write `templates/review.html` | 15m | ⬜ |
| 12 | Write `templates/calibration.html` | 20m | ⬜ |
| 13 | Write `static/style.css` | 10m | ⬜ |
| 14 | Write `Dockerfile` | 10m | ⬜ |
| 15 | Write `docker-compose.yml` | 5m | ⬜ |
| 16 | Write `tests/conftest.py` | 10m | ⬜ |
| 17 | Write `tests/test_app.py` | 20m | ⬜ |
| 18 | Write `tests/test_cstp_client.py` | 15m | ⬜ |
| 19 | Local testing | 20m | ⬜ |
| 20 | Docker build + test | 15m | ⬜ |
| 21 | Deploy to production | 15m | ⬜ |
| 22 | Verify in browser | 10m | ⬜ |

**Total estimated time:** ~5-6 hours

---

## 5. Deployment Commands

```bash
# Build
cd cognition-agent-decisions/dashboard
docker build -t cstp-dashboard:latest .

# Run standalone
docker run -d \
  --name cstp-dashboard \
  -p 8080:8080 \
  -e CSTP_URL=http://192.168.1.141:9991 \
  -e CSTP_TOKEN=your-token \
  -e DASHBOARD_USER=admin \
  -e DASHBOARD_PASS=your-password \
  -e SECRET_KEY=random-secret-key \
  cstp-dashboard:latest

# Or with docker-compose
docker-compose up -d

# View logs
docker logs -f cstp-dashboard

# Access
open http://localhost:8080
```
