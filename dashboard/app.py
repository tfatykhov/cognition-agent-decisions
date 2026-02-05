"""CSTP Dashboard Flask application."""
import asyncio
from typing import Any

from flask import Flask, Response, flash, redirect, render_template, request, url_for

from .auth import requires_auth
from .config import config
from .cstp_client import CSTPClient, CSTPError

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Initialize CSTP client
cstp = CSTPClient(config.cstp_url, config.cstp_token)

# Auth decorator bound to config
auth = requires_auth(config)


def run_async(coro: Any) -> Any:
    """Run async coroutine in sync Flask context.
    
    Args:
        coro: Async coroutine to run
        
    Returns:
        Result of the coroutine
    """
    return asyncio.run(coro)


@app.route("/health")
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


@app.route("/decisions")
@auth
def decisions() -> str:
    """List all decisions with pagination and filters.
    
    Query params:
        page: Page number (default 1)
        category: Filter by category
        status: Filter by status (pending/reviewed)
    """
    page = request.args.get("page", 1, type=int)
    per_page = 20
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    
    # Convert status to has_outcome boolean
    has_outcome: bool | None = None
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
    
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
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
    POST: Submit review
    
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
    """
    project = request.args.get("project") or None
    
    try:
        stats = run_async(cstp.get_calibration(project=project))
    except CSTPError as e:
        flash(f"Error loading calibration: {e}", "error")
        stats = None
    
    return render_template("calibration.html", stats=stats, project=project)


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
