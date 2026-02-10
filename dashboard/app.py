"""CSTP Dashboard Flask application."""
import contextlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import Flask, Response, flash, redirect, render_template, request, url_for
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from auth import requires_auth
from config import config
from cstp_client import CSTPClient, CSTPError
from models import CalibrationStats, Decision

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Enable CSRF protection
csrf = CSRFProtect(app)

# Initialize CSTP client (module-level, reused across requests for connection pooling)
cstp = CSTPClient(config.cstp_url, config.cstp_token)

# Auth decorator bound to config
auth = requires_auth(config)


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
    if cstp.health_check():
        return Response("OK", status=200)
    return Response("CSTP unavailable", status=503)


@app.route("/")
@auth
def index() -> str:
    """Overview dashboard with aggregated stats and date filtering."""
    # Parse date filter
    period = request.args.get("period", "today")
    custom_date = request.args.get("date")

    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "custom" and custom_date:
        try:
            date_from = datetime.fromisoformat(custom_date + "T00:00:00+00:00")
            date_to = date_from + timedelta(days=1)
        except ValueError:
            date_from = today
            date_to = today + timedelta(days=1)
    elif period == "week":
        date_from = today - timedelta(days=today.weekday())
        date_to = now + timedelta(seconds=1)
    elif period == "month":
        date_from = today.replace(day=1)
        date_to = now + timedelta(seconds=1)
    elif period == "all":
        date_from = None
        date_to = None
    else:
        # Default: today
        period = "today"
        date_from = today
        date_to = today + timedelta(days=1)

    # Fetch calibration stats (always all-time)
    stats = cstp.get_calibration()

    # Fetch all decisions for aggregation
    all_decisions, total_count = cstp.list_decisions(limit=200, search="all")

    # Apply date filter
    if date_from is not None:
        filtered = [
            d for d in all_decisions
            if d.created_at >= date_from and (date_to is None or d.created_at < date_to)
        ]
    else:
        filtered = all_decisions

    # All decisions shown (no 10-item cap)
    decisions_list = sorted(filtered, key=lambda d: d.created_at, reverse=True)

    # Category breakdown
    cat_counts: dict[str, int] = Counter(d.category for d in filtered)

    # Stakes breakdown
    stakes_counts: dict[str, int] = Counter(d.stakes for d in filtered)

    # Outcome breakdown
    outcome_counts: dict[str, int] = Counter(
        d.outcome if d.outcome else "pending" for d in filtered
    )

    # Tag cloud (top 20)
    tag_counter: Counter[str] = Counter()
    for d in filtered:
        for t in d.tags:
            tag_counter[t] += 1
    top_tags = tag_counter.most_common(20)

    # Quality distribution
    quality_buckets = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for d in filtered:
        if d.quality and d.quality.score is not None:
            if d.quality.score >= 0.7:
                quality_buckets["high"] += 1
            elif d.quality.score >= 0.4:
                quality_buckets["medium"] += 1
            else:
                quality_buckets["low"] += 1
        else:
            quality_buckets["none"] += 1

    return render_template(
        "overview.html",
        stats=stats,
        decisions_list=decisions_list,
        total=len(filtered),
        total_all=len(all_decisions),
        cat_counts=cat_counts,
        stakes_counts=stakes_counts,
        outcome_counts=outcome_counts,
        top_tags=top_tags,
        quality_buckets=quality_buckets,
        period=period,
        custom_date=custom_date or today.strftime("%Y-%m-%d"),
        today_str=today.strftime("%Y-%m-%d"),
    )


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
        all_decisions, _ = cstp.list_decisions(
            limit=200,
            offset=0,
            category=category,
            has_outcome=has_outcome,
            search=search,
        )
    except CSTPError:
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
        decision = cstp.get_decision(decision_id)
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
        decision = cstp.get_decision(decision_id)
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
                success = cstp.review_decision(
                    decision_id,
                    outcome,
                    actual_result,
                    lessons,
                )
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
        stats = cstp.get_calibration(project=project, window=window)
    except CSTPError as e:
        flash(f"Error loading calibration: {e}", "error")
    
    # Check for drift (only if not filtering by window)
    if not window:
        with contextlib.suppress(CSTPError):
            drift = cstp.check_drift(project=project)
    
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
