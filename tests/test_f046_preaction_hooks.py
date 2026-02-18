"""Tests for issue #120: pre_action auto_record hooks.

Verifies that pre_action with auto_record=true correctly runs
all 3 dispatcher hooks before calling record_decision:

1. Deliberation attachment (F023 Phase 2)
2. Related decisions extraction (F025)
3. Bridge extraction (F027 P2)
"""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.deliberation_tracker import (
    reset_tracker,
    track_query,
    track_reasoning,
)
from a2a.cstp.models import PreActionRequest


# ---------------------------------------------------------------------------
# Mock response dataclasses (reuse pattern from test_f046_pre_action.py)
# ---------------------------------------------------------------------------


@dataclass
class MockQueryResult:
    id: str = "abc12345"
    title: str = "Test decision"
    category: str = "architecture"
    confidence: float = 0.8
    stakes: str = "medium"
    status: str = "reviewed"
    outcome: str = "success"
    date: str = "2026-01-15"
    distance: float = 0.12
    reason_types: list[str] | None = None
    tags: list[str] | None = None
    pattern: str | None = None
    lessons: str | None = None
    actual_result: str | None = None
    reasons: list[dict[str, str]] | None = None


@dataclass
class MockQueryResponse:
    results: list[MockQueryResult] = field(default_factory=list)
    query: str = "test"
    query_time_ms: int = 10
    error: str | None = None


@dataclass
class MockGuardrailResult:
    guardrail_id: str
    name: str
    message: str
    severity: str
    suggestion: str | None = None


@dataclass
class MockEvalResult:
    allowed: bool = True
    violations: list[MockGuardrailResult] = field(default_factory=list)
    warnings: list[MockGuardrailResult] = field(default_factory=list)
    evaluated: int = 3


@dataclass
class MockCalibrationOverall:
    brier_score: float = 0.05
    accuracy: float = 0.90
    calibration_gap: float = -0.02
    interpretation: str = "well_calibrated"
    reviewed_decisions: int = 15
    total_decisions: int = 20


@dataclass
class MockCalibrationResponse:
    overall: MockCalibrationOverall | None = field(
        default_factory=MockCalibrationOverall,
    )
    by_confidence_bucket: list = field(default_factory=list)  # type: ignore[type-arg]
    recommendations: list = field(default_factory=list)  # type: ignore[type-arg]
    confidence_stats: None = None
    query_time: str = "2026-01-15T00:00:00"


@dataclass
class MockRecordResponse:
    success: bool = True
    id: str = "new12345"
    path: str = "decisions/2026/02/test.yaml"
    indexed: bool = True
    timestamp: str = "2026-02-14T00:00:00"
    error: str | None = None
    quality: dict | None = None  # type: ignore[type-arg]
    guardrail_warnings: list | None = None  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_deliberation_tracker() -> None:  # type: ignore[misc]
    """Reset the global tracker before each test to avoid leaking state."""
    reset_tracker()


# ---------------------------------------------------------------------------
# Hook 1: Deliberation attachment
# ---------------------------------------------------------------------------


class TestPreActionDeliberationAttachment:
    """Verify that accumulated record_thought calls get attached to the
    decision recorded by pre_action with auto_record=true."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_thoughts_attached_to_recorded_decision(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """Pre-decision thoughts tracked via track_reasoning should appear
        in the deliberation field of the RecordDecisionRequest."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="hook1234")

        agent_id = "test-delib-agent"
        tracker_key = f"rpc:{agent_id}"

        # Simulate pre-decision reasoning
        track_reasoning(tracker_key, "Considering option A vs B")
        track_reasoning(tracker_key, "Option A has better performance characteristics")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Choose option A for caching",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.85,
            },
        })
        resp = await pre_action(req, agent_id=agent_id)

        assert resp.allowed is True
        assert resp.decision_id == "hook1234"

        # Verify record_decision was called with deliberation attached
        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]
        assert record_req.deliberation is not None
        assert record_req.deliberation.has_content() is True

        # Should have at least 2 reasoning inputs
        reasoning_inputs = [
            inp for inp in record_req.deliberation.inputs
            if inp.source == "cstp:recordThought"
        ]
        assert len(reasoning_inputs) >= 2

        # Steps should reference reasoning
        reasoning_steps = [
            s for s in record_req.deliberation.steps
            if s.type == "reasoning"
        ]
        assert len(reasoning_steps) >= 2

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_no_thoughts_still_has_auto_deliberation(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """Even without explicit thoughts, pre_action tracks its own query/guardrail.

        Issue #159: pre_action now injects track_query/track_guardrail calls,
        so auto_attach_deliberation always has inputs to attach.
        """
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="nothought")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Simple action no thoughts",
                "category": "process",
                "confidence": 0.7,
            },
        })
        resp = await pre_action(req, agent_id="no-thought-agent")

        assert resp.decision_id == "nothought"
        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]
        # Issue #159: pre_action now tracks its own query+guardrail calls,
        # so deliberation should always have auto-captured content
        assert record_req.deliberation is not None
        assert record_req.deliberation.has_content() is True

        # Should have query and guardrail auto-tracked inputs
        sources = [inp.source for inp in record_req.deliberation.inputs]
        assert "cstp:queryDecisions" in sources
        assert "cstp:checkGuardrails" in sources

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_tracker_consumed_after_record(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """After pre_action records, the tracker session should be consumed
        (cleared) so the same thoughts don't attach to a future decision."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="consumed1")

        agent_id = "consume-agent"
        tracker_key = f"rpc:{agent_id}"

        track_reasoning(tracker_key, "This thought should be consumed")

        from a2a.cstp.deliberation_tracker import get_tracker
        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Test consumption",
                "category": "process",
                "confidence": 0.8,
            },
        })
        await pre_action(req, agent_id=agent_id)

        # After pre_action, tracker should have consumed the session
        tracker = get_tracker()
        remaining = tracker.get_inputs(tracker_key)
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Hook 2: Related decisions extraction
# ---------------------------------------------------------------------------


class TestPreActionRelatedDecisions:
    """Verify that query results from tracked inputs get extracted as
    related decisions on the recorded decision."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_query_results_populate_related(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When the tracker has query results with top_results, those should
        be extracted as related_to on the RecordDecisionRequest."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="related1")

        agent_id = "related-agent"
        tracker_key = f"rpc:{agent_id}"

        # Simulate a prior query that tracked results
        track_query(
            key=tracker_key,
            query="caching strategy",
            result_count=2,
            top_ids=["dec_aaa", "dec_bbb"],
            retrieval_mode="semantic",
            top_results=[
                {"id": "dec_aaa", "summary": "Used Redis for caching", "distance": 0.15},
                {"id": "dec_bbb", "summary": "Memcached vs Redis", "distance": 0.22},
            ],
        )

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Add caching layer",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.9,
            },
        })
        resp = await pre_action(req, agent_id=agent_id)

        assert resp.decision_id == "related1"
        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]

        # Should have related decisions populated from tracker
        assert len(record_req.related_to) >= 2
        related_ids = {r.id for r in record_req.related_to}
        assert "dec_aaa" in related_ids
        assert "dec_bbb" in related_ids

        # Check sorting by distance (closest first)
        distances = [r.distance for r in record_req.related_to]
        assert distances == sorted(distances)

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_no_prior_query_no_related(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When no prior query was tracked, related_to should remain empty."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="norel1")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Action without prior query",
                "category": "process",
                "confidence": 0.8,
            },
        })
        resp = await pre_action(req, agent_id="no-query-agent")

        assert resp.decision_id == "norel1"
        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]
        assert len(record_req.related_to) == 0

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_deduplicated_related_decisions(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When multiple queries return the same decision, it should be
        deduplicated (keeping the closest distance)."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="dedup1")

        agent_id = "dedup-agent"
        tracker_key = f"rpc:{agent_id}"

        # Two queries returning overlapping results
        track_query(
            key=tracker_key,
            query="auth patterns",
            result_count=1,
            top_ids=["dec_overlap"],
            retrieval_mode="semantic",
            top_results=[
                {"id": "dec_overlap", "summary": "JWT auth pattern", "distance": 0.30},
            ],
        )
        track_query(
            key=tracker_key,
            query="token validation",
            result_count=1,
            top_ids=["dec_overlap"],
            retrieval_mode="semantic",
            top_results=[
                {"id": "dec_overlap", "summary": "JWT auth pattern", "distance": 0.15},
            ],
        )

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Implement JWT validation",
                "category": "architecture",
                "confidence": 0.85,
            },
        })
        await pre_action(req, agent_id=agent_id)

        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]

        # Should be deduplicated to 1 entry
        assert len(record_req.related_to) == 1
        assert record_req.related_to[0].id == "dec_overlap"
        # Should keep the closer distance
        assert record_req.related_to[0].distance == 0.15


# ---------------------------------------------------------------------------
# Hook 3: Bridge extraction
# ---------------------------------------------------------------------------


class TestPreActionBridgeExtraction:
    """Verify that maybe_smart_extract_bridge runs on the recorded decision."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_bridge_auto_extracted_when_not_provided(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When no explicit bridge is provided, the bridge hook should
        attempt to auto-extract one from the decision text."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="bridge1")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Added Redis caching layer to reduce API latency",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.85,
            },
            "reasons": [
                {"type": "analysis", "text": "To reduce response times from 500ms to 50ms"},
            ],
        })
        resp = await pre_action(req, agent_id="bridge-agent")

        assert resp.decision_id == "bridge1"
        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]

        # Bridge should be auto-extracted (decision text has structure signals)
        assert record_req.bridge is not None
        assert record_req.bridge.has_content() is True

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_explicit_bridge_not_overwritten(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When an explicit bridge is provided via request, the hook
        should NOT overwrite it."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="bridge2")

        from a2a.cstp.preaction_service import pre_action

        # Note: PreActionRequest doesn't have a bridge field directly.
        # The bridge is only on RecordDecisionRequest. So explicit bridge
        # isn't possible via pre_action. Instead, test that the hook runs
        # by verifying maybe_smart_extract_bridge was called.
        req = PreActionRequest.from_params({
            "action": {
                "description": "Switched to JWT authentication to fix session issues",
                "category": "architecture",
                "stakes": "high",
                "confidence": 0.9,
            },
        })

        with patch(
            "a2a.cstp.bridge_hook.maybe_smart_extract_bridge",
            new_callable=AsyncMock,
        ) as mock_bridge:
            mock_bridge.return_value = (False, "none")
            resp = await pre_action(req, agent_id="bridge-explicit-agent")

            assert resp.decision_id == "bridge2"
            mock_bridge.assert_called_once()

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_bridge_hook_called_on_record_request(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """The bridge hook receives the RecordDecisionRequest object."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="bridge3")

        from a2a.cstp.decision_service import RecordDecisionRequest
        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Deploy monitoring stack",
                "category": "tooling",
                "confidence": 0.8,
            },
        })

        with patch(
            "a2a.cstp.bridge_hook.maybe_smart_extract_bridge",
            new_callable=AsyncMock,
        ) as mock_bridge:
            mock_bridge.return_value = (True, "rule")
            await pre_action(req, agent_id="bridge-type-agent")

            # Verify the hook was called with a RecordDecisionRequest
            mock_bridge.assert_called_once()
            call_arg = mock_bridge.call_args[0][0]
            assert isinstance(call_arg, RecordDecisionRequest)
            assert call_arg.decision == "Deploy monitoring stack"


# ---------------------------------------------------------------------------
# Combined: all 3 hooks in one flow
# ---------------------------------------------------------------------------


class TestPreActionAllHooksCombined:
    """Verify that all 3 hooks work together in a single pre_action call."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_all_hooks_fire_together(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """Full integration: thoughts + query results + bridge extraction
        should all be applied to the decision in a single pre_action call."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="all3hooks")

        agent_id = "combined-agent"
        tracker_key = f"rpc:{agent_id}"

        # Hook 1 setup: track reasoning thoughts
        track_reasoning(tracker_key, "Evaluating caching approaches for API layer")

        # Hook 2 setup: track query with top_results
        track_query(
            key=tracker_key,
            query="caching API",
            result_count=1,
            top_ids=["prior_dec1"],
            retrieval_mode="semantic",
            top_results=[
                {"id": "prior_dec1", "summary": "Redis caching decision", "distance": 0.10},
            ],
        )

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Added Redis caching to reduce latency for API calls",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.9,
            },
            "reasons": [
                {"type": "analysis", "text": "To reduce response times from 500ms to 50ms"},
                {"type": "empirical", "text": "Load tests show 10x improvement with caching"},
            ],
        })
        resp = await pre_action(req, agent_id=agent_id)

        assert resp.allowed is True
        assert resp.decision_id == "all3hooks"

        mock_record.assert_called_once()
        record_req = mock_record.call_args[0][0]

        # Hook 1: Deliberation attached
        assert record_req.deliberation is not None
        assert record_req.deliberation.has_content() is True
        # Should contain reasoning input
        reasoning_found = any(
            inp.source == "cstp:recordThought"
            for inp in record_req.deliberation.inputs
        )
        assert reasoning_found, "Reasoning thoughts should be in deliberation inputs"

        # Hook 2: Related decisions populated
        assert len(record_req.related_to) >= 1
        assert record_req.related_to[0].id == "prior_dec1"

        # Hook 3: Bridge extracted (decision text has structure+function signals)
        assert record_req.bridge is not None
        assert record_req.bridge.has_content() is True

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_hooks_skipped_when_auto_record_false(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When auto_record=false, no recording occurs and hooks are skipped."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()

        agent_id = "skip-agent"
        tracker_key = f"rpc:{agent_id}"

        # Set up tracker state that would normally trigger hooks
        track_reasoning(tracker_key, "Some thought")
        track_query(
            key=tracker_key,
            query="test",
            result_count=1,
            top_ids=["xyz"],
            retrieval_mode="semantic",
            top_results=[{"id": "xyz", "summary": "test", "distance": 0.1}],
        )

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Read-only check"},
            "options": {"autoRecord": False},
        })
        resp = await pre_action(req, agent_id=agent_id)

        assert resp.allowed is True
        assert resp.decision_id is None
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_hooks_skipped_when_blocked(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When guardrails block, recording and hooks are skipped."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(
            allowed=False,
            violations=[MockGuardrailResult(
                guardrail_id="g1",
                name="block-test",
                message="Blocked",
                severity="block",
            )],
        )
        mock_cal.return_value = MockCalibrationResponse()

        agent_id = "blocked-agent"
        tracker_key = f"rpc:{agent_id}"

        track_reasoning(tracker_key, "Some thought that should not be consumed")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Blocked action",
                "stakes": "high",
                "confidence": 0.3,
            },
        })
        resp = await pre_action(req, agent_id=agent_id)

        assert resp.allowed is False
        assert resp.decision_id is None
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_hook_failure_does_not_crash_preaction(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """If a hook (e.g. bridge extraction) raises, pre_action should
        still return gracefully (fail-open pattern)."""
        mock_query.return_value = MockQueryResponse()
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        # Make record_decision raise to test the try/except
        mock_record.side_effect = RuntimeError("unexpected hook failure")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Action that triggers hook failure",
                "category": "process",
                "confidence": 0.8,
            },
        })
        # Should NOT raise
        resp = await pre_action(req, agent_id="fail-agent")

        assert resp.allowed is True
        # Decision ID is None because record failed
        assert resp.decision_id is None
