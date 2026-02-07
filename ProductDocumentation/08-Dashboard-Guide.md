# Dashboard Guide

The Cognition Engines Dashboard is a Flask-based web UI for browsing decisions, reviewing outcomes, and monitoring calibration.

---

## Overview

| Feature | Route | Description |
|---------|-------|-------------|
| Decision List | `/decisions` | Paginated list with category/status filters |
| Decision Detail | `/decisions/<id>` | Full decision view with metadata and context |
| Outcome Review | `/decisions/<id>/review` | Form to record success/failure outcomes |
| Calibration | `/calibration` | Brier scores, confidence buckets, drift alerts |
| Health Check | `/health` | Backend connectivity status |

---

## Prerequisites

The dashboard requires:

- Python 3.11+
- Flask + Flask-WTF
- A running CSTP server (the dashboard is a client, not a server replacement)

### Install Dashboard Dependencies

```bash
pip install flask flask-wtf httpx
```

---

## Starting the Dashboard

### Option 1: Standalone

```bash
cd dashboard
python app.py
```

Dashboard starts on `http://localhost:5001` by default.

### Option 2: With Configuration

Set environment variables before starting:

```bash
$env:DASHBOARD_CSTP_URL = "http://localhost:8100"
$env:DASHBOARD_CSTP_TOKEN = "myagent:mysecrettoken"
$env:DASHBOARD_SECRET_KEY = "your-flask-secret-key"
$env:DASHBOARD_PORT = "5001"
python dashboard/app.py
```

---

## Dashboard Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_CSTP_URL` | `http://localhost:8100` | CSTP server URL |
| `DASHBOARD_CSTP_TOKEN` | — | Bearer token for CSTP API |
| `DASHBOARD_SECRET_KEY` | (random) | Flask session secret key |
| `DASHBOARD_PORT` | `5001` | Dashboard HTTP port |
| `DASHBOARD_USERNAME` | — | HTTP Basic Auth username |
| `DASHBOARD_PASSWORD` | — | HTTP Basic Auth password |

---

## Pages

### Decisions List (`/decisions`)

Displays a paginated table of all recorded decisions.

**Filters:**

- **Category** — Select a specific decision category
- **Status** — `pending` (awaiting review) or `reviewed` (outcome recorded)

**Pagination:** 20 decisions per page with page navigation.

### Decision Detail (`/decisions/<id>`)

Shows complete decision information:

- Decision text, category, confidence, stakes
- Reasons with type and strength
- Project context (project, feature, PR, files)
- Alternatives considered
- Outcome and review data (if reviewed)
- Timestamps (created, reviewed)

### Outcome Review (`/decisions/<id>/review`)

A form to record what actually happened after a decision was made:

| Field | Required | Description |
|-------|----------|-------------|
| Outcome | ✅ | `success`, `failure`, `partial`, `abandoned` |
| Actual Result | ✅ | What actually happened |
| Lessons Learned | ❌ | Key takeaways for future decisions |

CSRF protection is enabled on this form.

### Calibration Dashboard (`/calibration`)

Displays calibration metrics computed from reviewed decisions:

- **Overall Brier Score** — Lower is better (< 0.1 = excellent, < 0.2 = good)
- **Confidence Buckets** — Predicted vs. actual success rates by confidence range
- **Accuracy** — Overall success rate
- **Drift Alerts** — If recent performance diverges from historical baseline

**Filters:**

- **Project** — Filter by project name
- **Window** — Time window: 30d, 60d, 90d

---

## Security

- **HTTP Basic Auth:** Protects all routes (configurable username/password)
- **CSRF Protection:** Flask-WTF CSRF tokens on all form submissions
- **Session Management:** Secure cookie-based sessions

---

## Architecture

```
┌──────────────┐     HTTP/JSON-RPC     ┌──────────────────┐
│   Dashboard  │  ──────────────────▶  │   CSTP Server    │
│   (Flask)    │                        │   (FastAPI)      │
│   Port 5001  │  ◀──────────────────  │   Port 8100      │
│              │     JSON responses     │                  │
└──────────────┘                        └──────────────────┘
```

The dashboard is a **thin client** — it communicates with the CSTP server via the same JSON-RPC API that agents use. It adds:

- HTML rendering via Jinja2 templates
- Form handling for outcome reviews
- Human-friendly data presentation
