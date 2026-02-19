"""Sync client for CSTP JSON-RPC API."""
from typing import Any

import httpx

from models import CalibrationStats, Decision, GraphNeighbor


class CSTPError(Exception):
    """CSTP API error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class CSTPClient:
    """Sync client for CSTP server.
    
    Uses a shared httpx.Client for connection pooling and keep-alive.
    Create once at module level, reuse across requests.
    
    Example:
        client = CSTPClient("http://localhost:9991", "token")
        decisions, total = client.list_decisions(limit=10)
    """
    
    def __init__(self, base_url: str, token: str) -> None:
        """Initialize CSTP client.
        
        Args:
            base_url: CSTP server URL (e.g., http://localhost:9991)
            token: Authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._request_id = 0
        self._http_client = httpx.Client(timeout=30.0, headers=self.headers)
    
    def close(self) -> None:
        """Close the HTTP client."""
        self._http_client.close()
    
    def _next_id(self) -> int:
        """Generate next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id
    
    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make JSON-RPC call to CSTP server.
        
        Args:
            method: JSON-RPC method name (e.g., cstp.queryDecisions)
            params: Method parameters
            
        Returns:
            Result dictionary from JSON-RPC response
            
        Raises:
            CSTPError: If API returns an error
            httpx.HTTPError: If HTTP request fails
        """
        response = self._http_client.post(
            f"{self.base_url}/cstp",
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
            error = data["error"]
            raise CSTPError(
                error.get("message", "Unknown error"),
                error.get("code"),
            )
        
        return data.get("result", {})
    
    def list_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        stakes: str | None = None,
        status: str | None = None,
        search: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[Decision], int]:
        """List decisions with server-side filtering, sorting, and pagination.

        Uses cstp.listDecisions (SQL-backed) for structured queries.

        Args:
            limit: Maximum number of decisions to return (1-500)
            offset: Number of decisions to skip (for pagination)
            category: Filter by category (architecture, process, etc.)
            stakes: Filter by stakes level (low, medium, high, critical)
            status: Filter by review status (pending, reviewed)
            search: Keyword search (SQL FTS, not semantic)
            sort: Sort column (created_at, confidence, category, stakes, status)
            order: Sort direction (asc, desc)
            date_from: ISO date string for start of range
            date_to: ISO date string for end of range

        Returns:
            Tuple of (list of Decision objects, total count)
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if stakes:
            params["stakes"] = stakes
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if sort != "created_at":
            params["sort"] = sort
        if order != "desc":
            params["order"] = order
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

        result = self._call("cstp.listDecisions", params)

        decisions = [Decision.from_dict(d) for d in result.get("decisions", [])]
        total = result.get("total", len(decisions))

        return decisions, total

    def search_decisions(
        self,
        query: str,
        limit: int = 20,
        category: str | None = None,
        has_outcome: bool | None = None,
        project: str | None = None,
    ) -> tuple[list[Decision], int]:
        """Semantic search over decisions using vector similarity.

        Uses cstp.queryDecisions (ChromaDB-backed) for semantic queries.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            category: Optional category filter
            has_outcome: Filter by review status (True=reviewed, False=pending)
            project: Filter by project (owner/repo format)

        Returns:
            Tuple of (list of Decision objects, total count)
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if category:
            params["category"] = category
        if has_outcome is not None:
            params["hasOutcome"] = has_outcome
        if project:
            params["project"] = project

        result = self._call("cstp.queryDecisions", params)

        decisions = [Decision.from_dict(d) for d in result.get("decisions", [])]
        total = result.get("total", len(decisions))

        return decisions, total

    def get_stats(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated decision statistics from server.

        Uses cstp.getStats (SQL-backed) for efficient aggregation.

        Args:
            date_from: ISO date string for start of range
            date_to: ISO date string for end of range
            project: Optional project filter

        Returns:
            Raw stats dict with keys: total, byCategory, byStakes,
            byStatus, byAgent, byDay, topTags, recentActivity
        """
        params: dict[str, Any] = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if project:
            params["project"] = project

        return self._call("cstp.getStats", params)
    
    def get_decision(self, decision_id: str) -> Decision | None:
        """Get single decision by ID using getDecision API.
        
        Args:
            decision_id: Decision ID (full or prefix)
            
        Returns:
            Decision object if found, None otherwise
        """
        result = self._call("cstp.getDecision", {"id": decision_id})
        
        if result.get("found") and result.get("decision"):
            return Decision.from_dict(result["decision"])
        
        return None
    
    def review_decision(
        self,
        decision_id: str,
        outcome: str,
        actual_result: str,
        lessons: str | None = None,
    ) -> bool:
        """Submit outcome review for a decision.
        
        Args:
            decision_id: Decision ID to review
            outcome: Outcome status (success, partial, failure, abandoned)
            actual_result: Description of what actually happened
            lessons: Optional lessons learned
            
        Returns:
            True if review was recorded successfully
        """
        params: dict[str, Any] = {
            "id": decision_id,
            "outcome": outcome,
            "actual_result": actual_result,
        }
        if lessons:
            params["lessons"] = lessons
        
        result = self._call("cstp.reviewDecision", params)
        return result.get("status") == "reviewed"
    
    def get_calibration(
        self,
        project: str | None = None,
        category: str | None = None,
        window: str | None = None,
    ) -> CalibrationStats:
        """Get calibration statistics.
        
        Args:
            project: Optional project filter
            category: Optional category filter
            window: Time window ("30d", "60d", "90d", or None for all-time)
            
        Returns:
            CalibrationStats with overall and per-category metrics
        """
        params: dict[str, Any] = {}
        if project:
            params["project"] = project
        if category:
            params["category"] = category
        if window:
            params["window"] = window
        
        result = self._call("cstp.getCalibration", params)
        return CalibrationStats.from_dict(result)
    
    def check_drift(
        self,
        threshold_brier: float = 0.20,
        threshold_accuracy: float = 0.15,
        category: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Check for calibration drift between recent and historical periods.
        
        Args:
            threshold_brier: Brier degradation threshold (default 20%)
            threshold_accuracy: Accuracy drop threshold (default 15%)
            category: Optional category filter
            project: Optional project filter
            
        Returns:
            Drift check results with alerts and recommendations
        """
        params: dict[str, Any] = {
            "thresholdBrier": threshold_brier,
            "thresholdAccuracy": threshold_accuracy,
        }
        if category:
            params["category"] = category
        if project:
            params["project"] = project
        
        return self._call("cstp.checkDrift", params)
    
    def debug_tracker(self, key: str | None = None,
                      include_consumed: bool = False) -> dict[str, Any]:
        """Get deliberation tracker debug state.

        Args:
            key: Optional tracker key to filter by
            include_consumed: Include recently consumed/expired sessions

        Returns:
            Tracker debug data with sessions and detail
        """
        params: dict[str, Any] = {}
        if key:
            params["key"] = key
        if include_consumed:
            params["includeConsumed"] = True
        return self._call("cstp.debugTracker", params)

    def get_neighbors(self, decision_id: str, limit: int = 20) -> list[GraphNeighbor]:
        """Get graph neighbors of a decision."""
        result = self._call("cstp.getNeighbors", {
            "nodeId": decision_id[:8],
            "direction": "both",
            "limit": limit,
        })

        neighbors: list[GraphNeighbor] = []
        for item in result.get("neighbors", []):
            node = item.get("node", {})
            edge = item.get("edge", {})
            direction = "outgoing" if edge.get("sourceId") == decision_id[:8] else "incoming"
            neighbors.append(GraphNeighbor(
                id=node.get("id", ""),
                summary=node.get("summary", ""),
                category=node.get("category", ""),
                stakes=node.get("stakes", ""),
                date=node.get("date", ""),
                edge_type=edge.get("edgeType", ""),
                weight=float(edge.get("weight", 0.0)),
                direction=direction,
            ))
        return neighbors

    def health_check(self) -> bool:
        """Check if CSTP server is reachable.
        
        Returns:
            True if server responds to health check
        """
        try:
            response = self._http_client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False
