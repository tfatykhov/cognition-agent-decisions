"""Async client for CSTP JSON-RPC API."""
from typing import Any

import httpx

from .models import CalibrationStats, Decision


class CSTPError(Exception):
    """CSTP API error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class CSTPClient:
    """Async client for CSTP server.
    
    Provides methods to interact with CSTP JSON-RPC API for decision
    intelligence operations. Uses a shared httpx.AsyncClient for
    connection pooling.
    
    Example:
        client = CSTPClient("http://localhost:9991", "token")
        async with client:
            decisions, total = await client.list_decisions(limit=10)
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
        self._http_client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "CSTPClient":
        """Enter async context manager."""
        self._http_client = httpx.AsyncClient(timeout=30.0, headers=self.headers)
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.
        
        Returns shared client if in context manager, otherwise creates new one.
        """
        if self._http_client:
            return self._http_client
        # Fallback for non-context-manager usage (creates new client per call)
        return httpx.AsyncClient(timeout=30.0, headers=self.headers)
    
    def _next_id(self) -> int:
        """Generate next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id
    
    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
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
        client = self._get_client()
        should_close = self._http_client is None
        
        try:
            response = await client.post(
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
        finally:
            if should_close:
                await client.aclose()
    
    async def list_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        has_outcome: bool | None = None,
        project: str | None = None,
    ) -> tuple[list[Decision], int]:
        """List decisions with optional filters.
        
        Args:
            limit: Maximum number of decisions to return
            offset: Number of decisions to skip (for pagination)
            category: Filter by category (architecture, process, etc.)
            has_outcome: Filter by review status (True=reviewed, False=pending)
            project: Filter by project (owner/repo format)
            
        Returns:
            Tuple of (list of Decision objects, total count)
        """
        params: dict[str, Any] = {
            "query": "",
            "top_k": limit,
        }
        if category:
            params["category"] = category
        if has_outcome is not None:
            params["hasOutcome"] = has_outcome
        if project:
            params["project"] = project
        
        result = await self._call("cstp.queryDecisions", params)
        
        decisions = [Decision.from_dict(d) for d in result.get("decisions", [])]
        total = result.get("total", len(decisions))
        
        return decisions, total
    
    async def get_decision(self, decision_id: str) -> Decision | None:
        """Get single decision by ID.
        
        Args:
            decision_id: Decision ID (full or prefix)
            
        Returns:
            Decision object if found, None otherwise
        """
        result = await self._call("cstp.queryDecisions", {
            "query": decision_id,
            "top_k": 10,
        })
        
        for d in result.get("decisions", []):
            if d["id"].startswith(decision_id):
                return Decision.from_dict(d)
        
        return None
    
    async def review_decision(
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
        
        result = await self._call("cstp.reviewDecision", params)
        return result.get("status") == "reviewed"
    
    async def get_calibration(
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
        
        result = await self._call("cstp.getCalibration", params)
        return CalibrationStats.from_dict(result)
    
    async def health_check(self) -> bool:
        """Check if CSTP server is reachable.
        
        Returns:
            True if server responds to health check
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
