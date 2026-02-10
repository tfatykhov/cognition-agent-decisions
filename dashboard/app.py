"""CSTP Dashboard Flask application."""
import asyncio
import contextlib
from typing import Any

from flask import Flask, Response, flash, redirect, render_template, request, url_for
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from auth import requires_auth
from config import config
from cstp_client import CSTPClient, CSTPError

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Enable CSRF protection
csrf = CSRFProtect(app)

# Initialize CSTP client
cstp = CSTPClient(config.cstp_url, config.cstp_token)

# Auth decorator bound to config
auth = requires_auth(config)


def run_async(coro: Any) -> Any:
    """Run async coroutine in sync Flask context.
    
    Note: Flask 2.0+ supports async views natively, but gunicorn
    with sync workers requires this wrapper. For production with
    async support, use an ASGI server like uvicorn.
    
    Args:
        coro: Async coroutine to run
        
    Returns:
        Result of the coroutine
    """
    return asyncio.run(coro)


@app.errorhandler(CSRFError)
def handle_csrf_error(e: CSRFError) -> tuple[str, int]:
    """Handle CSRF validation errors."""
    flash("Session expired. Please try again.", "error")
    return redirect(url_for("decisions")), 400


@app.route("/health")
@csrf.exempt  # Health check doesn't need CSRF
def health() -> Response:
    """Health check endpoint (no auth required).
    
    Returns 200 OK if CSTP server is reachable, 503 otherwise.
    """
    healthy = run_async(cstp.health_check())
    if healthy:
        return Response("OK", status=200)
    return Response("CSTP unavailable", status=503)


@app.route("/")
@auth
def index() -> Response:
    """Redirect root to decisions list."""
    return redirect(url_for("decisions"))


def _get_decisions(
    page: int = 1,
    per_page: int = 20,
    category: str | None = None,
    status: str | None = None,
    stakes: str | None = None,
    search: str | None = None,
    sort: str | None = None,
) -> tuple[list, int, int, int]:
    """Shared logic for fetching, filtering, sorting, and paginating decisions.

    Fetches a large batch from the API, applies client-side filters
    (stakes, status) and sorting, then paginates.

    Returns:
        (page_decisions, total, page, total_pages)
    """
    has_outcome: bool | None = None
    if status == "pending":
        has_outcome = False
    elif status == "reviewed":
        has_outcome = True

    try:
        # Fetch larger batch for client-side filtering/sorting
        all_decisions, _ = run_async(cstp.list_decisions(
            limit=200,
            offset=0,
            category=category,
            has_outcome=has_outcome,
            search=search,
        ))
    except CSTPError as e:
        return [], 0, page, 1

    # Client-side filtering for stakes (API doesn't support it)
    if stakes:
        all_decisions = [d for d in all_decisions if d.stakes == stakes]

    # Client-side sorting
    if sort:
        if sort == "confidence":
            all_decisions.sort(key=lambda d: d.confidence, reverse=True)
        elif sort == "-confidence":
            all_decisions.sort(key=lambda d: d.confidence)
        elif sort == "category":
            all_decisions.sort(key=lambda d: d.category)
        elif sort == "-date":
            all_decisions.sort(key=lambda d: d.created_at)

    total = len(all_decisions)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_decisions = all_decisions[start : start + per_page]

    return page_decisions, total, page, total_pages


@app.route("/decisions")
@auth
def decisions() -> str:
    """List all decisions with pagination and filters."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    stakes = request.args.get("stakes") or None
    search = request.args.get("search") or None
    sort = request.args.get("sort") or None

    decision_list, total, page, total_pages = _get_decisions(
        page=page, category=category, status=status,
        stakes=stakes, search=search, sort=sort,
    )

    return render_template(
        "decisions.html",
        decisions=decision_list,
        page=page,
        total_pages=total_pages,
        total=total,
        category=category,
        status=status,
        stakes=stakes,
        search=search,
        sort=sort,
    )


@app.route("/decisions/partial")
@auth
def decisions_partial() -> str:
    """Return just the table rows for HTMX partial swap."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    stakes = request.args.get("stakes") or None
    search = request.args.get("search") or None
    sort = request.args.get("sort") or None

    decision_list, total, page, total_pages = _get_decisions(
        page=page, category=category, status=status,
        stakes=stakes, search=search, sort=sort,
    )

    return render_template(
        "decisions_partial.html",
        decisions=decision_list,
        page=page,
        total_pages=total_pages,
        total=total,
        category=category,
        status=status,
        stakes=stakes,
        search=search,
        sort=sort,
    )


@app.route("/decisions/<decision_id>")
@auth
def decision_detail(decision_id: str) -> str | Response:
    """View single decision details.
    
    Args:
        decision_id: Decision ID (full or prefix)
    """
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
def review(decision_id: str) -> str | Response:
    """Review decision outcome.
    
    GET: Show review form
    POST: Submit review (CSRF protected)
    
    Args:
        decision_id: Decision ID to review
    """
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
def calibration() -> str:
    """Calibration dashboard showing accuracy metrics.
    
    Query params:
        project: Optional project filter
        window: Time window (30d, 60d, 90d)
    """
    project = request.args.get("project") or None
    window = request.args.get("window") or None
    
    stats = None
    drift = None
    
    try:
        stats = run_async(cstp.get_calibration(project=project, window=window))
    except CSTPError as e:
        flash(f"Error loading calibration: {e}", "error")
    
    # Check for drift (only if not filtering by window)
    if not window:
        with contextlib.suppress(CSTPError):
            drift = run_async(cstp.check_drift(project=project))
    
    return render_template(
        "calibration.html",
        stats=stats,
        project=project,
        window=window,
        drift=drift,
    )


def main() -> None:
    """Run development server."""
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"Config error: {error}")
        return
    
    app.run(host="0.0.0.0", port=config.dashboard_port, debug=True)


if __name__ == "__main__":
    main()
