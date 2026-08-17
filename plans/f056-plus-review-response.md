# F056+ — Response to the Five-Lens Review

**Source:** CAD Deep Team Analysis (DAG `dcd725ab`), 2026-08-16, reviewed at `9151ef1`.
**Validated:** 2026-08-16 against `9151ef1` (= merge of PR #197; the review covers current `main`).
**Status:** Plan. Nothing here is implemented.

---

## Part 1 — Validation

Every file:line claim in the review was checked against the tree. The review is unusually
accurate: it measured rather than estimated.

### Confirmed exactly

| Claim | Verified |
|---|---|
| `mcp_server.py` 32% coverage (399 stmts / 271 missed) | exact |
| `vectordb/chromadb.py` 17% (148 / 123) | exact |
| `provenance_service.py` 55%, lines 390-649 untested | exact |
| `bm25_index.py` 22% (105 / 82) | exact |
| 1329 passed / 3 skipped, 78% total | exact |
| `a2a/cstp/tests/` = 47 tests, all pass, excluded by `testpaths = ["tests"]` | exact |
| `dashboard/tests/` uncollectable — `ModuleNotFoundError: No module named 'auth'` | exact |
| 17 MCP tools vs 34 registered RPC methods | exact |
| `dispatcher.py` 1617 lines; reaches `from .storage.factory` at :940 and :982 | exact |
| `CSTP_STORAGE` defaults to `yaml` (`config.py:198`) | confirmed |
| `cors_origins = ["*"]` + `allow_credentials=True` | confirmed |
| CEL evaluator returns `False` on any eval error (fail open) | confirmed |
| `save_edges_to_jsonl` full rewrite via `path.open("w")`, non-atomic | confirmed |
| `_sessions` process-local dict; `uvicorn.run()` with no `workers=` | confirmed |
| `RATE_LIMITED = -32002` defined twice, zero implementation | confirmed |
| No OpenTelemetry anywhere (the `demo/seed_data.py` hits are seeded decision *text*) | confirmed |
| No mypy in CI despite `[tool.mypy]` config; no `--cov-fail-under` | confirmed |
| Three version strings: `pyproject` 0.15.0, README v0.16.0, `CSTP_AGENT_VERSION=0.7.0` | confirmed |
| Agent card served only at `/.well-known/agent.json` | confirmed |
| `chromadb.py` lazy-imports both `httpx` (:51) and `urllib.request` (:64) | confirmed |
| `ingest_evidence` takes `source` from caller params with no verification | confirmed |

### Corrections

**1. The headline finding does not survive contact with the Dockerfile.**

The review's single highest-confidence item (C1 / G1) is "a live RCE risk." It is not, in any
shipped artifact.

```python
# dashboard/app.py
def main() -> None:
    """Run development server."""
    errors = config.validate()          # <-- the ONLY empty-password guard
    if errors: ...; return
    app.run(host="0.0.0.0", ..., debug=True)   # <-- the RCE vector

if __name__ == "__main__":
    main()
```

```dockerfile
# dashboard/Dockerfile:30
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--access-logfile", "-", "app:app"]
```

Gunicorn imports `app:app`. `main()` never runs. Therefore:

- **`debug=True` never executes in the container.** No Werkzeug debugger, no RCE. The review's
  Critical severity is overstated — this is a dev-path-only line.
- **`config.validate()` never executes either.** The review flagged this as a hypothetical
  ("*if* the app is run under a WSGI server that imports `app`"). It is not hypothetical: that is
  precisely and exclusively how the image ships. The empty-password guard is dead code in every
  containerized deployment.

Tempering it back down: the production `docker-compose.yml` has **no dashboard service at all**
(only `cstp-server` and `chromadb`), and `demo/docker-compose.yml` sets `DASHBOARD_PASS=demo`.
So the exposure is *anyone self-hosting the dashboard image without setting `DASHBOARD_PASS`* —
real and undefended, but not open-by-default in what we ship.

**Net: G1 is High, not Critical, and the reason is the auth guard, not the debugger.** The fix
is cheap either way, so this changes the *justification* more than the priority.

**2. G32 / Architecture #12 — the nested stale directory does not exist.**
`./cognition-agent-decisions/` is not in the repo. The reviewer worked from
`/tmp/nous-workspace/cognition-agent-decisions` and saw their own clone's parent path. Drop it.

**3. G26 contradicts itself.** It reads "No CodeQL / container scan in CI **despite Dependabot
already configured**." There is no `.github/dependabot.yml`; `.github/` contains exactly
`workflows/ci.yml` and `workflows/deploy-website.yml`. The Quality lens got this right (§3.5);
the synthesis got it wrong. Scope must *add* Dependabot, not assume it.

**4. `severity:` is a phantom field.** F057's scope says "fail-closed for `severity: block` CEL
guardrails." Guardrail YAML has no `severity` key — the wire field is `action: block|warn|log`,
and `severity` is derived from it at `guardrails_service.py:610` (`severity=g.action`). A spec
written against `severity:` would produce a rule that never matches.

**5. `drift_service.py` is 34%, not 44%** (76 stmts / 50 missed here vs 90 / 50 claimed) —
statement-count delta from a different Python version. Immaterial, noted for accuracy.

### The review's own biggest omission

**`uv.lock` is broken and never reached the ranked gap register.** The Quality lens called it
"verified severe" (§3.3) but it appears nowhere in G1–G32, so anyone implementing the register
verbatim would skip it.

- `uv.lock` pins the package at **0.7.0**; `pyproject.toml` is at 0.15.0 — eight minor versions stale.
- `rank-bm25`, `networkx`, and `cel-python` — all declared **required core dependencies** — have
  **zero** `[[package]]` entries in the lockfile. Verified by direct grep: `0`, `0`, `0`.
- `uv sync --locked` today yields an environment where BM25 retrieval, the decision graph, and
  CEL guardrail evaluation all fail to import.

This belongs in the first workstream.

### Not verifiable from the repo

**The SR 26-2 claim.** The Market lens asserts SR 26-2 (April 17, 2026) superseded SR 11-7 and
explicitly excludes generative/agentic AI from scope, citing three dated sources. I cannot confirm
this from the codebase, and it postdates what I can reliably attest to. What I *can* confirm is the
blast radius if true: `SR 11-7` appears in `README.md`, `website/changelog.md`,
`website/reference/api.md`, `website/specs/f055-decision-provenance.md`, `docs/features/INDEX.md`,
`a2a/cstp/provenance_service.py`, and the rule file `a2a/cstp/provenance/mappings/sr11-7.yaml`
(whose `framework:` string is literally `"SR 11-7"`).

**Gate the doc rewrite on human confirmation of the SR 26-2 claim.** Do not auto-execute it.

---

## Part 2 — Implementation Plan

Resequenced from the review's F056–F062. Two changes of substance: CI truth splits out ahead of
everything (it is the enabler and touches no production code), and the two cheap durability
one-liners move up (they prevent total data loss for less effort than items ranked above them).

### F056 — CI Truth & Supply Chain · effort S · no production code

CI currently reports a number that is not true of the codebase. Fix the instrument before
trusting any reading from it. Everything downstream depends on this.

1. `testpaths = ["tests", "a2a/cstp/tests"]` — 47 already-green tests become visible.
2. Fix `dashboard/tests` collection: `dashboard/app.py:12` does `from auth import requires_auth`
   (implicit relative import). Make it `from dashboard.auth import ...` and add
   `dashboard/__init__.py`, or add a `conftest.py` `sys.path` entry. Then add `dashboard/tests`
   to CI.
3. **Regenerate or delete `uv.lock`.** A lockfile that omits three required deps is worse than
   none — it makes `uv sync --locked` produce a silently broken env. If the project is not
   actually using uv, delete it.
4. Add a `mypy src/ a2a/` step — config exists and has never run.
5. Add `--cov-fail-under=75` (below the current 78 so it ratchets rather than blocks).
6. Add `.github/dependabot.yml` and a CodeQL workflow.

**Verify:** CI green with ≥1376 tests collected (1329 + 47); `--cov-fail-under` passes; mypy step
runs (allowed to fail-soft on first landing if the backlog is large — record the count).

**Risk:** mypy on a never-type-checked tree may produce hundreds of errors. Land it
`continue-on-error: true` with a tracked count, then ratchet.

### F057 — Dashboard Auth Hardening · effort S

Reframed per validation: the bug is the guard that never runs, not the debugger.

1. Call `config.validate()` at **module import**, not in `main()` — this is the actual defect.
   Raise/exit hard on empty `DASHBOARD_PASS`.
2. `secrets.compare_digest` for both username and password (`a2a/config.py:52` already does this
   correctly for CSTP tokens — mirror it).
3. `debug=False` unless an explicit `DASHBOARD_DEBUG` env var is set (defense in depth for the
   dev path).
4. Login attempt throttling.
5. CORS: default `cors_origins` to `[]`, drop `allow_credentials=True` unless the dashboard
   genuinely needs cookie auth — and if so, scope it to the dashboard origin only.

**Verify:** a test that imports `dashboard.app` with `DASHBOARD_PASS` unset and asserts it raises;
a test asserting empty-password login is rejected.

### F058 — Durability Quick Wins · effort S

Pulled forward from the review's lower ranks. Both are small and both prevent whole-dataset loss.

1. `save_edges_to_jsonl` → write to `path.with_suffix(".tmp")` then `os.replace()`. Today a crash
   mid-write truncates the **entire** graph, not the in-flight edge.
2. Flip `CSTP_STORAGE` default to `sqlite`; keep `yaml` as explicit opt-in; log a loud startup
   warning when running on YAML.
3. Refuse to boot when `workers > 1` while `DeliberationTracker` is in-memory (cheap guard now;
   real persistence is F062).

**Verify:** a test that kills mid-write and asserts the prior graph survives; a startup test
asserting the YAML warning fires.

### F059 — Guardrail Fail-Closed + Rate Limiting + Admin Tier · effort M

The review's F057, with the phantom-field correction.

1. Fail **closed** for guardrails with `action: block` (not `severity: block` — see Correction 4).
   Eval errors on a blocking rule must block or escalate, never silently pass.
2. Promote CEL compile/eval failures to a counter/metric, not just `_logger.warning`.
3. Per-token rate-limit middleware; actually raise the already-reserved `RATE_LIMITED = -32002`.
4. Admin-vs-agent token tier gating `resetCircuit`, `setPreserve`, `compact`, `reindex`,
   `debugTracker`, `mapControls`.

**Verify:** a test that a malformed CEL expression on an `action: block` rule blocks rather than
passes — this is the regression that matters most.

### F060 — Scoped Tokens & Per-Agent Tenancy · effort M

1. `scopes` / `tenant` / `expires_at` on `AuthToken`.
2. Thread tenant through `ListQuery` / `load_all_decisions`; default-deny cross-tenant reads.
3. Revocation list so a leaked token dies without a restart.

**Verify:** two tokens, two tenants, each can only read its own decisions.

### F061 — Eval Harness · effort S/M

The Quality lens rates this the highest-leverage gap in the review, and it is right: the product
claim ("agents decide better with this") is currently unfalsifiable from the repo. Ship the two
cheap metrics; treat the counterfactual as its own project.

1. **Guardrail precision/recall** — 100-200 labeled `(action, should_block)` cases through
   `check_guardrails()`; report a confusion matrix. ~1 day, zero production code.
2. **Retrieval Recall@k / MRR** — seed via `demo/seed_data.py`, hand-label 20-30 queries.
   ~1-2 days.

Land as `tests/eval/`, wired into CI **reporting-only** at first.

### F062 — Deferred / Larger

| Item | Effort | Note |
|---|---|---|
| MCP parity (17 missing wrappers) + dispatcher decorator refactor | M | Do the decorator *during* this, per the review's own T4 — don't grow the surface first |
| Tracker persistence (Redis or SQLite + TTL) | M | Unblocks multi-worker |
| OpenTelemetry span export | M | Market-validated; opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Provenance ingest credential + external anchoring | M/L | The forgeable-`observed` gap |
| Zero-dependency local quickstart | M | Fold `embeddings/ollama.py` in here |
| SR 11-7 → SR 26-2 doc correction | S | **Blocked on confirming the claim** |

### Explicitly not building

Agreed with the review, all four: `vectordb/weaviate.py` and `pgvector.py` (harden the 17%-covered
ChromaDB backend first), `embeddings/openai.py` (a second paid vendor does not fix the no-local-
option problem), F049 Live Deliberation Viewer (new surface on the least-tested component), and
F043 Distributed Merge (assumes multi-worker support that does not exist).

---

## Sequencing

```
F056 (CI truth)  ──┬──> F057 (dashboard auth)   S
                   ├──> F058 (durability)       S
                   └──> F059 (guardrails/RL)    M ──> F060 (tenancy)  M
                                                 └──> F061 (eval)     S/M
```

F056 first and alone: it is the only item that makes the others verifiable. F057 and F058 are
independent S-effort patches that can land in parallel immediately after. F059 gates F060.
F061 can start any time after F056 — it is purely additive.
