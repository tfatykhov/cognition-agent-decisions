# F011 Implementation Phases

## Phase 1: Foundation (30 min)
Create project structure and core configuration.

| Task | File | Est. |
|------|------|------|
| 1.1 | Create directory structure | 5m |
| 1.2 | `requirements.txt` | 2m |
| 1.3 | `pyproject.toml` | 5m |
| 1.4 | `config.py` - env config dataclass | 10m |
| 1.5 | `models.py` - Decision, CalibrationStats | 8m |

**Deliverable:** Project scaffolding complete, can import modules.

---

## Phase 2: CSTP Client (30 min)
Async client to communicate with CSTP server.

| Task | File | Est. |
|------|------|------|
| 2.1 | `cstp_client.py` - base class, `_call()` method | 10m |
| 2.2 | `list_decisions()` method | 8m |
| 2.3 | `get_decision()` method | 5m |
| 2.4 | `review_decision()` method | 5m |
| 2.5 | `get_calibration()` method | 5m |

**Deliverable:** Client can fetch decisions and calibration from CSTP.

---

## Phase 3: Flask App Core (45 min)
Flask app with auth and basic routes.

| Task | File | Est. |
|------|------|------|
| 3.1 | `auth.py` - Basic auth decorator | 10m |
| 3.2 | `app.py` - Flask app, health check | 10m |
| 3.3 | `app.py` - `/decisions` route | 10m |
| 3.4 | `app.py` - `/decisions/<id>` route | 8m |
| 3.5 | `app.py` - `/decisions/<id>/review` route | 10m |
| 3.6 | `app.py` - `/calibration` route | 7m |

**Deliverable:** All routes functional, returning data (no templates yet).

---

## Phase 4: Templates (45 min)
Jinja2 templates with Pico.css styling.

| Task | File | Est. |
|------|------|------|
| 4.1 | `templates/base.html` - layout, nav | 10m |
| 4.2 | `templates/decisions.html` - list with filters | 12m |
| 4.3 | `templates/decision.html` - detail view | 10m |
| 4.4 | `templates/review.html` - outcome form | 10m |
| 4.5 | `templates/calibration.html` - stats dashboard | 10m |
| 4.6 | `static/style.css` - custom overrides | 5m |

**Deliverable:** Full UI rendered in browser.

---

## Phase 5: Docker (20 min)
Containerize the application.

| Task | File | Est. |
|------|------|------|
| 5.1 | `Dockerfile` - multi-stage, healthcheck | 10m |
| 5.2 | `docker-compose.yml` - standalone | 5m |
| 5.3 | `.dockerignore` | 2m |
| 5.4 | Test build locally | 3m |

**Deliverable:** Docker image builds and runs.

---

## Phase 6: Testing (25 min)
Basic test coverage.

| Task | File | Est. |
|------|------|------|
| 6.1 | `tests/conftest.py` - fixtures | 8m |
| 6.2 | `tests/test_app.py` - route tests | 12m |
| 6.3 | `tests/test_cstp_client.py` - client tests | 5m |

**Deliverable:** Tests pass, basic coverage.

---

## Phase 7: Deploy & Verify (15 min)
Deploy to production environment.

| Task | Action | Est. |
|------|--------|------|
| 7.1 | Build production image | 3m |
| 7.2 | Deploy container | 5m |
| 7.3 | Verify all pages in browser | 5m |
| 7.4 | Test review workflow end-to-end | 2m |

**Deliverable:** Dashboard live and functional.

---

## Summary

| Phase | Description | Time |
|-------|-------------|------|
| 1 | Foundation | 30m |
| 2 | CSTP Client | 30m |
| 3 | Flask App Core | 45m |
| 4 | Templates | 45m |
| 5 | Docker | 20m |
| 6 | Testing | 25m |
| 7 | Deploy & Verify | 15m |
| **Total** | | **~3.5h** |

---

## Execution Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
   ↓         ↓         ↓         ↓         ↓         ↓         ↓
 Setup    Client    Routes   Templates  Docker    Tests    Deploy
```

Ready to start Phase 1?
