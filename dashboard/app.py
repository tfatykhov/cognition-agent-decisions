"""CSTP Dashboard Flask application."""
import contextlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
    tz_name = request.args.get("tz") or request.cookies.get("tz") or "America/New_York"

    try:
        user_tz = ZoneInfo(tz_name)
    except (KeyError, ValueError):
        user_tz = ZoneInfo("America/New_York")

    # Calculate "now" and "today" in the user's timezone
    now_utc = datetime.now(UTC)
    now_local = now_utc.astimezone(user_tz)
    today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "custom" and custom_date:
        try:
            # Parse as local date, convert to UTC
            local_dt = datetime.strptime(custom_date, "%Y-%m-%d").replace(tzinfo=user_tz)
            date_from = local_dt.astimezone(UTC)
            date_to = (local_dt + timedelta(days=1)).astimezone(UTC)
        except ValueError:
            date_from = today_local.astimezone(UTC)
            date_to = (today_local + timedelta(days=1)).astimezone(UTC)
    elif period == "week":
        week_start = today_local - timedelta(days=today_local.weekday())
        date_from = week_start.astimezone(UTC)
        date_to = now_utc + timedelta(seconds=1)
    elif period == "month":
        month_start = today_local.replace(day=1)
        date_from = month_start.astimezone(UTC)
        date_to = now_utc + timedelta(seconds=1)
    elif period == "all":
        date_from = None
        date_to = None
    else:
        # Default: today in user's timezone
        period = "today"
        date_from = today_local.astimezone(UTC)
        date_to = (today_local + timedelta(days=1)).astimezone(UTC)

    # Fetch calibration stats (always all-time)
    stats = cstp.get_calibration()

    # Fetch all decisions for aggregation
    all_decisions, total_count = cstp.list_decisions(limit=500)

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
        custom_date=custom_date or today_local.strftime("%Y-%m-%d"),
        today_str=today_local.strftime("%Y-%m-%d"),
        tz_name=tz_name,
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

    # Client-side sorting (default: newest first)
    if sort == "confidence":
        all_decisions.sort(key=lambda d: d.confidence, reverse=True)
    elif sort == "-confidence":
        all_decisions.sort(key=lambda d: d.confidence)
    elif sort == "category":
        all_decisions.sort(key=lambda d: d.category)
    elif sort == "-date":
        all_decisions.sort(key=lambda d: d.created_at)
    else:
        # Default: newest first
        all_decisions.sort(key=lambda d: d.created_at, reverse=True)

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

    # Fetch graph neighbors (error-isolated — never break the page)
    graph_neighbors: list = []
    with contextlib.suppress(Exception):
        graph_neighbors = cstp.get_neighbors(decision_id)

    return render_template(
        "decision.html",
        decision=decision,
        graph_neighbors=graph_neighbors,
    )


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


def parse_tracker_key(key: str) -> dict[str, str | None]:
    """Parse composite tracker key into display components."""
    result: dict[str, str | None] = {
        "agent_id": None, "decision_id": None,
        "transport": None, "transport_id": None, "raw": key,
    }
    if key.startswith("agent:") and ":decision:" in key:
        parts = key.split(":decision:")
        result["agent_id"] = parts[0].removeprefix("agent:")
        result["decision_id"] = parts[1]
    elif key.startswith("agent:"):
        result["agent_id"] = key.removeprefix("agent:")
    elif key.startswith("decision:"):
        result["decision_id"] = key.removeprefix("decision:")
    elif ":" in key:
        transport, _, transport_id = key.partition(":")
        result["transport"] = transport
        result["transport_id"] = transport_id
    return result


def _transform_tracker_sessions(tracker_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform raw debugTracker response into template-friendly dicts."""
    sessions = []
    detail = tracker_data.get("detail", {})
    for key in tracker_data.get("sessions", []):
        session_detail = detail.get(key, {})
        parsed = parse_tracker_key(key)
        inputs = []
        for inp in session_detail.get("inputs", []):
            age = inp.get("ageSeconds", 0)
            inputs.append({
                **inp,
                "age_display": _format_age(age),
                "age_class": _age_freshness_class(age),
            })
        raw_inputs = session_detail.get("inputs", [])
        sessions.append({
            "key": key, "parsed": parsed,
            "input_count": session_detail.get("inputCount", 0), "inputs": inputs,
            "freshness": _session_freshness_class(raw_inputs),
        })
    return sessions


def _format_age(seconds: int) -> str:
    """Format age in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"


def _age_freshness_class(seconds: int) -> str:
    """Return CSS class based on age freshness.

    Thresholds per F049 spec:
    - active (green): < 60s
    - stale (yellow): 60-300s
    - orphaned (red): > 300s (5min)
    """
    if seconds < 60:
        return "age--fresh"
    if seconds < 300:
        return "age--stale"
    return "age--orphaned"


def _session_freshness_class(inputs: list[dict[str, Any]]) -> str:
    """Return session-level CSS class based on newest input age."""
    if not inputs:
        return "age--orphaned"
    min_age = min(inp.get("ageSeconds", 0) for inp in inputs)
    return _age_freshness_class(min_age)


def _transform_consumed_sessions(consumed_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform consumed session records into template-friendly dicts."""
    sessions = []
    for item in consumed_data:
        parsed = parse_tracker_key(item.get("key", ""))
        age = item.get("consumedAt", 0)
        sessions.append({
            "key": item.get("key", ""),
            "parsed": parsed,
            "input_count": item.get("inputCount", 0),
            "agent_id": item.get("agentId"),
            "decision_id": item.get("decisionId"),
            "status": item.get("status", "consumed"),
            "age_display": _format_age(age),
            "age_class": _age_freshness_class(age),
            "inputs_summary": item.get("inputsSummary", []),
        })
    return sessions


@app.route("/deliberation")
@auth
def deliberation() -> str:
    """Live deliberation tracker viewer."""
    filter_key = request.args.get("key") or None
    try:
        tracker_data = cstp.debug_tracker(key=filter_key, include_consumed=True)
    except CSTPError as e:
        flash(f"Error loading tracker: {e}", "error")
        tracker_data = {"sessions": [], "sessionCount": 0, "detail": {}}
    sessions = _transform_tracker_sessions(tracker_data)
    consumed = _transform_consumed_sessions(tracker_data.get("consumed", []))
    return render_template(
        "deliberation.html",
        sessions=sessions,
        consumed=consumed,
        session_count=tracker_data.get("sessionCount", 0),
        filter_key=filter_key,
    )


@app.route("/deliberation/partial")
@auth
def deliberation_partial() -> str:
    """Partial template for HTMX auto-refresh."""
    filter_key = request.args.get("key") or None
    try:
        tracker_data = cstp.debug_tracker(key=filter_key, include_consumed=True)
    except CSTPError:
        tracker_data = {"sessions": [], "sessionCount": 0, "detail": {}}
    sessions = _transform_tracker_sessions(tracker_data)
    consumed = _transform_consumed_sessions(tracker_data.get("consumed", []))
    return render_template(
        "deliberation_partial.html",
        sessions=sessions,
        consumed=consumed,
        session_count=tracker_data.get("sessionCount", 0),
        filter_key=filter_key,
    )


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
