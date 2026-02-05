# F011 Implementation Plan: Web Dashboard

**Spec:** `docs/specs/F011-WEB-DASHBOARD.md`  
**Skill:** python-pro (type-safe Python 3.11+)  
**Decision ID:** cd235c3e  

---

## Overview

Build a Flask-based web dashboard for CSTP with:
- HTTP Basic Auth
- Decision list/detail views
- Outcome review form
- Calibration dashboard

**Constraints (from python-pro):**
- Type hints for all functions and classes
- Dataclasses for models
- Async where beneficial (httpx for CSTP calls)
- pytest for testing
- Google-style docstrings
- No hardcoded secrets (env vars only)

---

## Phase 1: Project Setup

### 1.1 Directory Structure

```bash
mkdir -p dashboard/{templates,static,tests}
touch dashboard/{__init__,app,config,cstp_client,models,auth}.py
touch dashboard/templates/{base,decisions,decision,review,calibration,login}.html
touch dashboard/static/style.css
touch dashboard/{Dockerfile,requirements.txt,pyproject.toml}
touch dashboard/tests/{__init__,test_app,test_cstp_client,conftest}.py
```

**Files to create:**
| File | Purpose |
|------|---------|
| `app.py` | Flask app, routes, entry point |
| `config.py` | Environment config with dataclass |
| `cstp_client.py` | Async CSTP API wrapper |
| `models.py` | Decision, Calibration dataclasses |
| `auth.py` | Basic auth decorator |
| `Dockerfile` | Container build |
| `requirements.txt` | Dependencies |
| `pyproject.toml` | Project metadata, ruff/mypy config |

### 1.2 Dependencies

```txt
# requirements.txt
flask>=3.0
httpx>=0.27
python-dotenv>=1.0
gunicorn>=21.0
```

### 1.3 Config Dataclass

```python
# config.py
from dataclasses import dataclass
from os import environ

@dataclass(frozen=True)
class Config:
    """Dashboard configuration from environment."""
    cstp_url: str = environ.get("CSTP_URL", "http://localhost:9991")
    cstp_token: str = environ.get("CSTP_TOKEN", "")
    dashboard_user: str = environ.get("DASHBOARD_USER", "admin")
    dashboard_pass: str = environ.get("DASHBOARD_PASS", "")
    dashboard_port: int = int(environ.get("DASHBOARD_PORT", "8080"))
    secret_key: str = environ.get("SECRET_KEY", "dev-secret-change-me")
```

---

## Phase 2: CSTP Client

### 2.1 Models

```python
# models.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ProjectContext:
    project: str | None = None
    feature: str | None = None
    pr: int | None = None
    file: str | None = None
    line: int | None = None
    commit: str | None = None

@dataclass
class Decision:
    id: str
    summary: str
    category: str
    stakes: str
    confidence: float
    created_at: datetime
    outcome: str | None = None
    actual_result: str | None = None
    lessons: str | None = None
    reviewed_at: datetime | None = None
    project_context: ProjectContext | None = None

@dataclass
class CalibrationStats:
    total_decisions: int
    reviewed_decisions: int
    brier_score: float
    accuracy: float
    calibration_status: str
    by_category: dict[str, dict]
```

### 2.2 Async Client

```python
# cstp_client.py
import httpx
from models import Decision, CalibrationStats

class CSTPClient:
    """Async client for CSTP JSON-RPC API."""
    
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def _call(self, method: str, params: dict) -> dict:
        """Make JSON-RPC call to CSTP server."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/cstp",
                headers=self.headers,
                json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
            )
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                raise Exception(result["error"]["message"])
            return result["result"]
    
    async def list_decisions(
        self, 
        limit: int = 50, 
        offset: int = 0,
        category: str | None = None,
        has_outcome: bool | None = None
    ) -> list[Decision]:
        """List decisions with optional filters."""
        # May need cstp.listDecisions or use queryDecisions with empty query
        ...
    
    async def get_decision(self, decision_id: str) -> Decision:
        """Get single decision by ID."""
        ...
    
    async def review_decision(
        self, 
        decision_id: str, 
        outcome: str, 
        actual_result: str,
        lessons: str | None = None
    ) -> bool:
        """Submit outcome review for decision."""
        result = await self._call("cstp.reviewDecision", {
            "decision_id": decision_id,
            "outcome": outcome,
            "actual_result": actual_result,
            "lessons": lessons
        })
        return result.get("success", False)
    
    async def get_calibration(
        self, 
        project: str | None = None,
        category: str | None = None
    ) -> CalibrationStats:
        """Get calibration statistics."""
        result = await self._call("cstp.getCalibration", {
            "project": project,
            "category": category
        })
        return CalibrationStats(**result)
```

---

## Phase 3: Flask App

### 3.1 Auth Decorator

```python
# auth.py
from functools import wraps
from flask import request, Response
from config import Config

def check_auth(username: str, password: str, config: Config) -> bool:
    """Validate credentials against config."""
    return username == config.dashboard_user and password == config.dashboard_pass

def requires_auth(config: Config):
    """Decorator for Basic Auth protection."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, config):
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": 'Basic realm="CSTP Dashboard"'}
                )
            return f(*args, **kwargs)
        return decorated
    return decorator
```

### 3.2 Routes

```python
# app.py
import asyncio
from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from cstp_client import CSTPClient
from auth import requires_auth

config = Config()
app = Flask(__name__)
app.secret_key = config.secret_key
cstp = CSTPClient(config.cstp_url, config.cstp_token)
auth = requires_auth(config)

def run_async(coro):
    """Run async coroutine in sync Flask context."""
    return asyncio.run(coro)

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
    category = request.args.get("category")
    status = request.args.get("status")  # pending/reviewed
    
    decisions = run_async(cstp.list_decisions(
        limit=20,
        offset=(page - 1) * 20,
        category=category,
        has_outcome=None if status is None else (status == "reviewed")
    ))
    
    return render_template("decisions.html", decisions=decisions, page=page)

@app.route("/decisions/<decision_id>")
@auth
def decision_detail(decision_id: str):
    """View single decision."""
    decision = run_async(cstp.get_decision(decision_id))
    return render_template("decision.html", decision=decision)

@app.route("/decisions/<decision_id>/review", methods=["GET", "POST"])
@auth
def review(decision_id: str):
    """Review decision outcome."""
    if request.method == "POST":
        outcome = request.form.get("outcome")
        actual_result = request.form.get("actual_result")
        lessons = request.form.get("lessons")
        
        success = run_async(cstp.review_decision(
            decision_id, outcome, actual_result, lessons
        ))
        
        if success:
            flash("Outcome recorded successfully", "success")
            return redirect(url_for("decision_detail", decision_id=decision_id))
        else:
            flash("Failed to record outcome", "error")
    
    decision = run_async(cstp.get_decision(decision_id))
    return render_template("review.html", decision=decision)

@app.route("/calibration")
@auth
def calibration():
    """Calibration dashboard."""
    stats = run_async(cstp.get_calibration())
    return render_template("calibration.html", stats=stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.dashboard_port, debug=True)
```

---

## Phase 4: Templates

### 4.1 Base Layout

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}CSTP Dashboard{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="container">
        <ul>
            <li><strong>CSTP Dashboard</strong></li>
        </ul>
        <ul>
            <li><a href="{{ url_for('decisions') }}">Decisions</a></li>
            <li><a href="{{ url_for('calibration') }}">Calibration</a></li>
        </ul>
    </nav>
    <main class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <article class="{{ category }}">{{ message }}</article>
            {% endfor %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="container">
        <small>CSTP Dashboard v0.1.0</small>
    </footer>
</body>
</html>
```

### 4.2 Decisions List

```html
<!-- templates/decisions.html -->
{% extends "base.html" %}
{% block title %}Decisions - CSTP Dashboard{% endblock %}
{% block content %}
<h1>Decisions</h1>

<form method="get" role="group">
    <select name="category">
        <option value="">All Categories</option>
        <option value="architecture">Architecture</option>
        <option value="process">Process</option>
        <option value="integration">Integration</option>
        <option value="tooling">Tooling</option>
        <option value="security">Security</option>
    </select>
    <select name="status">
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="reviewed">Reviewed</option>
    </select>
    <button type="submit">Filter</button>
</form>

<table>
    <thead>
        <tr>
            <th>ID</th>
            <th>Summary</th>
            <th>Category</th>
            <th>Confidence</th>
            <th>Outcome</th>
        </tr>
    </thead>
    <tbody>
        {% for d in decisions %}
        <tr>
            <td><a href="{{ url_for('decision_detail', decision_id=d.id) }}">{{ d.id[:8] }}</a></td>
            <td>{{ d.summary[:60] }}{% if d.summary|length > 60 %}...{% endif %}</td>
            <td>{{ d.category }}</td>
            <td>{{ "%.0f"|format(d.confidence * 100) }}%</td>
            <td>
                {% if d.outcome %}
                    {{ d.outcome }}
                {% else %}
                    <a href="{{ url_for('review', decision_id=d.id) }}">⏳ Review</a>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<nav>
    {% if page > 1 %}
        <a href="?page={{ page - 1 }}" role="button">← Previous</a>
    {% endif %}
    <span>Page {{ page }}</span>
    <a href="?page={{ page + 1 }}" role="button">Next →</a>
</nav>
{% endblock %}
```

---

## Phase 5: Docker

### 5.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "app:app"]
```

### 5.2 Docker Compose Addition

```yaml
# Add to existing docker-compose.yml
  dashboard:
    build: ./dashboard
    ports:
      - "8080:8080"
    environment:
      - CSTP_URL=http://cstp:9991
      - CSTP_TOKEN=${CSTP_TOKEN}
      - DASHBOARD_USER=${DASHBOARD_USER}
      - DASHBOARD_PASS=${DASHBOARD_PASS}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - cstp
```

---

## Phase 6: Testing

### 6.1 Test Config

```python
# tests/conftest.py
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers():
    import base64
    creds = base64.b64encode(b"admin:testpass").decode()
    return {"Authorization": f"Basic {creds}"}
```

### 6.2 Route Tests

```python
# tests/test_app.py
def test_index_redirects(client, auth_headers):
    response = client.get("/", headers=auth_headers)
    assert response.status_code == 302

def test_decisions_requires_auth(client):
    response = client.get("/decisions")
    assert response.status_code == 401

def test_decisions_with_auth(client, auth_headers):
    response = client.get("/decisions", headers=auth_headers)
    assert response.status_code == 200
```

---

## Implementation Order

| Step | Task | Est. Time | Dependencies |
|------|------|-----------|--------------|
| 1 | Create directory structure | 5 min | None |
| 2 | Write `config.py` + `models.py` | 15 min | None |
| 3 | Write `cstp_client.py` | 30 min | Models |
| 4 | Write `auth.py` | 10 min | Config |
| 5 | Write `app.py` routes | 45 min | Client, Auth |
| 6 | Write `base.html` template | 15 min | None |
| 7 | Write `decisions.html` | 20 min | Base |
| 8 | Write `decision.html` | 15 min | Base |
| 9 | Write `review.html` | 15 min | Base |
| 10 | Write `calibration.html` | 20 min | Base |
| 11 | Write `style.css` | 10 min | None |
| 12 | Write Dockerfile | 10 min | None |
| 13 | Write tests | 30 min | App |
| 14 | Test locally | 20 min | All |
| 15 | Deploy + verify | 15 min | All |

**Total estimated time:** ~4-5 hours

---

## CSTP API Gap

The current CSTP API may need a new method for listing decisions without semantic search:

```json
{
  "method": "cstp.listDecisions",
  "params": {
    "limit": 50,
    "offset": 0,
    "category": "architecture",
    "hasOutcome": false,
    "orderBy": "created_at",
    "orderDir": "desc"
  }
}
```

**Alternative:** Use `cstp.queryDecisions` with an empty query string and rely on metadata filters.

---

## Acceptance Checklist

- [ ] `dashboard/` directory structure created
- [ ] Config loads from environment
- [ ] CSTP client connects and fetches data
- [ ] Basic auth protects all routes
- [ ] Decision list displays with pagination
- [ ] Decision detail shows all fields
- [ ] Review form submits outcome
- [ ] Calibration page shows stats
- [ ] Dockerfile builds successfully
- [ ] Tests pass
- [ ] Deployed and accessible
