# F011: Web Dashboard

**Status:** Draft  
**Priority:** P1  
**Decision ID:** 467c593e  

## Summary

Create a web dashboard for CSTP that allows users to view decisions, review outcomes, and monitor calibration — all through a browser interface.

## Motivation

Currently CSTP is CLI-only (`scripts/cstp.py`). A web dashboard provides:
- Visual overview of decision history
- Easier outcome review (click instead of CLI)
- Calibration trends at a glance
- Multi-agent decision comparison
- Accessible to users who prefer GUI over terminal

## Requirements

### Functional

#### F011.1: Decision List View
- Paginated list of all decisions
- Columns: ID, summary (truncated), category, stakes, confidence, outcome, created_at
- Sort by: date (default), confidence, stakes
- Filter by: category, stakes, outcome status (pending/reviewed), agent

#### F011.2: Decision Detail View
- Full decision text
- All metadata (category, stakes, confidence, project context)
- Outcome section (if reviewed)
- Edit button to update outcome

#### F011.3: Outcome Review Form
- Dropdown: success / partial / failure / abandoned
- Text field: actual_result
- Text field: lessons (optional)
- Submit updates decision via CSTP API

#### F011.4: Calibration Dashboard
- Overall stats: total decisions, reviewed count, Brier score, accuracy
- Per-category breakdown table
- Per-agent breakdown (if multi-agent)
- Simple bar chart for category accuracy (optional, stretch goal)

#### F011.5: Authentication
- HTTP Basic Auth for MVP
- Single username/password from environment variables
- All routes protected

### Non-Functional

#### F011.6: Deployment
- Separate Docker container
- Dockerfile in `dashboard/`
- Environment variables for config:
  - `CSTP_URL` — CSTP server URL (default: http://cstp:9991)
  - `CSTP_TOKEN` — API token for dashboard
  - `DASHBOARD_USER` — Basic auth username
  - `DASHBOARD_PASS` — Basic auth password
  - `DASHBOARD_PORT` — Listen port (default: 8080)

#### F011.7: Tech Stack
- **Backend:** Python 3.11+ with Flask or FastAPI
- **Frontend:** Server-side rendered HTML (Jinja2 templates)
- **Styling:** Simple CSS (no build step) — Pico.css or similar minimal framework
- **No JavaScript frameworks** — keep it simple, progressive enhancement only

## Architecture

```
┌─────────────────┐     HTTP/JSON-RPC     ┌─────────────────┐
│   Dashboard     │ ───────────────────▶  │   CSTP Server   │
│   (Flask)       │                       │   (FastAPI)     │
│   Port 8080     │ ◀───────────────────  │   Port 9991     │
└─────────────────┘                       └─────────────────┘
        │
        │ Basic Auth
        ▼
    Browser
```

### API Calls (Dashboard → CSTP)

| Dashboard Action | CSTP Method |
|------------------|-------------|
| List decisions | `cstp.queryDecisions` with empty query, high limit |
| Get decision | `cstp.queryDecisions` with ID filter (or new method) |
| Update outcome | `cstp.reviewDecision` |
| Get calibration | `cstp.getCalibration` |

### New CSTP Method (Optional)

May need `cstp.listDecisions` for paginated listing without semantic search:

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.listDecisions",
  "params": {
    "limit": 50,
    "offset": 0,
    "category": "architecture",
    "hasOutcome": false
  },
  "id": 1
}
```

## File Structure

```
dashboard/
├── Dockerfile
├── requirements.txt
├── app.py                 # Flask app entry point
├── config.py              # Environment config
├── cstp_client.py         # CSTP API wrapper
├── templates/
│   ├── base.html          # Layout with nav
│   ├── decisions.html     # List view
│   ├── decision.html      # Detail view
│   ├── review.html        # Outcome form
│   └── calibration.html   # Stats dashboard
└── static/
    └── style.css          # Minimal custom CSS
```

## UI Mockups

### Decision List (`/decisions`)

```
┌──────────────────────────────────────────────────────────────┐
│  CSTP Dashboard                          [Calibration] [Logout]
├──────────────────────────────────────────────────────────────┤
│  Decisions (43 total, 28 reviewed)                           │
│                                                              │
│  Filter: [Category ▼] [Stakes ▼] [Status ▼] [Agent ▼]       │
│                                                              │
│  ┌────────┬──────────────────────────┬──────┬───────┬──────┐│
│  │ ID     │ Summary                  │ Cat  │ Conf  │ Out  ││
│  ├────────┼──────────────────────────┼──────┼───────┼──────┤│
│  │ 467c.. │ Create web dashboard...  │ arch │ 0.85  │  ⏳  ││
│  │ 85e9.. │ Configure sub-agents...  │ intg │ 0.85  │  ⏳  ││
│  │ 88c1.. │ Keep CSTP in TOOLS.md... │ proc │ 0.85  │  ✅  ││
│  └────────┴──────────────────────────┴──────┴───────┴──────┘│
│                                                              │
│  [← Prev]  Page 1 of 3  [Next →]                            │
└──────────────────────────────────────────────────────────────┘
```

### Decision Detail (`/decisions/<id>`)

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back to list                                              │
├──────────────────────────────────────────────────────────────┤
│  Decision: 467c593e                                          │
│                                                              │
│  Summary:                                                    │
│  Create web dashboard for CSTP as separate Docker service    │
│  with basic auth, decision viewing, and outcome review       │
│                                                              │
│  ┌─────────────┬─────────────────────────────────────────┐  │
│  │ Category    │ architecture                            │  │
│  │ Stakes      │ medium                                  │  │
│  │ Confidence  │ 0.85                                    │  │
│  │ Created     │ 2026-02-05 19:18:00                     │  │
│  │ Agent       │ emerson                                 │  │
│  └─────────────┴─────────────────────────────────────────┘  │
│                                                              │
│  Outcome: ⏳ Pending review                                  │
│                                                              │
│  [Review Outcome]                                            │
└──────────────────────────────────────────────────────────────┘
```

### Review Form (`/decisions/<id>/review`)

```
┌──────────────────────────────────────────────────────────────┐
│  Review Decision: 467c593e                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Outcome:  [success ▼]                                       │
│            ○ success                                         │
│            ○ partial                                         │
│            ○ failure                                         │
│            ○ abandoned                                       │
│                                                              │
│  What happened:                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Dashboard deployed, working well...                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Lessons learned (optional):                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Pico.css saved time, no build step was the right...  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Cancel]  [Submit Review]                                   │
└──────────────────────────────────────────────────────────────┘
```

### Calibration (`/calibration`)

```
┌──────────────────────────────────────────────────────────────┐
│  Calibration Dashboard                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Overall Stats                                               │
│  ┌────────────────┬────────────────┬────────────────┐       │
│  │ Total: 43      │ Reviewed: 28   │ Pending: 15    │       │
│  │ Brier: 0.04    │ Accuracy: 91%  │ Status: ✅     │       │
│  └────────────────┴────────────────┴────────────────┘       │
│                                                              │
│  By Category                                                 │
│  ┌──────────────┬─────────┬──────────┬──────────┐          │
│  │ Category     │ Count   │ Accuracy │ Brier    │          │
│  ├──────────────┼─────────┼──────────┼──────────┤          │
│  │ architecture │ 12      │ 92%      │ 0.03     │          │
│  │ process      │ 18      │ 89%      │ 0.05     │          │
│  │ integration  │ 8       │ 100%     │ 0.00     │          │
│  │ tooling      │ 3       │ 67%      │ 0.12     │          │
│  └──────────────┴─────────┴──────────┴──────────┘          │
│                                                              │
│  By Agent                                                    │
│  ┌──────────────┬─────────┬──────────┐                      │
│  │ Agent        │ Count   │ Accuracy │                      │
│  ├──────────────┼─────────┼──────────┤                      │
│  │ emerson      │ 35      │ 91%      │                      │
│  │ codereviewer │ 5       │ 100%     │                      │
│  │ docsagent    │ 3       │ 100%     │                      │
│  └──────────────┴─────────┴──────────┘                      │
└──────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Core Dashboard
1. Create `dashboard/` directory structure
2. Implement Flask app with Basic Auth
3. Create CSTP client wrapper
4. Build decision list view
5. Build decision detail view

### Phase 2: Review Workflow
6. Build outcome review form
7. Wire up to `cstp.reviewDecision`
8. Add success/error feedback

### Phase 3: Calibration
9. Build calibration dashboard
10. Add per-category breakdown
11. Add per-agent breakdown (if data available)

### Phase 4: Deployment
12. Create Dockerfile
13. Add to docker-compose.yml
14. Document deployment

## Testing

- Manual testing via browser
- Test auth (valid/invalid credentials)
- Test decision CRUD flow
- Test outcome update persists

## Security Considerations

- Basic Auth over HTTPS only in production
- CSTP token stored as environment variable, not in code
- No sensitive data in logs
- Rate limiting (future enhancement)

## Future Enhancements

- OAuth/SSO integration
- Calibration trend charts (time series)
- Decision search (semantic via CSTP)
- Export to CSV
- Dark mode toggle
- Mobile responsive design

## Acceptance Criteria

- [ ] Dashboard accessible at configured port
- [ ] Basic Auth protects all routes
- [ ] Can view paginated decision list
- [ ] Can filter by category, stakes, outcome status
- [ ] Can view decision details
- [ ] Can submit outcome review
- [ ] Calibration page shows overall + per-category stats
- [ ] Runs as Docker container
- [ ] No JavaScript build step required
