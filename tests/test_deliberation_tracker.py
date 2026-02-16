"""Tests for F023 Phase 2 — DeliberationTracker auto-capture."""

import time

from a2a.cstp.decision_service import (
    Deliberation,
    DeliberationInput,
    DeliberationStep,
)
from a2a.cstp.deliberation_tracker import (
    DeliberationTracker,
    TrackedInput,
    auto_attach_deliberation,
    get_tracker,
    reset_tracker,
    track_guardrail,
    track_lookup,
    track_query,
    track_stats,
)


class TestDeliberationTracker:
    """Core tracker tests."""

    def test_track_and_consume(self):
        tracker = DeliberationTracker(input_ttl=60)
        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-abc",
                type="query",
                text="Queried 'test': 3 results",
                source="cstp:queryDecisions",
                timestamp=time.time(),
                raw_data={"query": "test", "result_count": 3},
            ),
        )

        delib = tracker.consume("agent:test")
        assert delib is not None
        assert len(delib.inputs) == 1
        assert delib.inputs[0].id == "q-abc"
        assert delib.inputs[0].source == "cstp:queryDecisions"
        assert len(delib.steps) == 1
        assert delib.steps[0].inputs_used == ["q-abc"]

    def test_consume_clears(self):
        tracker = DeliberationTracker(input_ttl=60)
        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-1",
                type="query",
                text="test",
                source="cstp:queryDecisions",
                timestamp=time.time(),
                raw_data={},
            ),
        )

        # First consume returns data
        delib = tracker.consume("agent:test")
        assert delib is not None

        # Second consume returns None
        delib2 = tracker.consume("agent:test")
        assert delib2 is None

    def test_multiple_agents_isolated(self):
        tracker = DeliberationTracker(input_ttl=60)
        now = time.time()

        tracker.track(
            "rpc:emerson",
            TrackedInput(
                id="q-em",
                type="query",
                text="Emerson query",
                source="cstp:queryDecisions",
                timestamp=now,
                raw_data={},
            ),
        )
        tracker.track(
            "rpc:code-reviewer",
            TrackedInput(
                id="q-cr",
                type="query",
                text="Reviewer query",
                source="cstp:queryDecisions",
                timestamp=now,
                raw_data={},
            ),
        )

        # Emerson's consume only gets emerson's inputs
        delib_em = tracker.consume("rpc:emerson")
        assert delib_em is not None
        assert len(delib_em.inputs) == 1
        assert delib_em.inputs[0].id == "q-em"

        # Reviewer's inputs are still there
        delib_cr = tracker.consume("rpc:code-reviewer")
        assert delib_cr is not None
        assert len(delib_cr.inputs) == 1
        assert delib_cr.inputs[0].id == "q-cr"

    def test_ttl_expiry(self):
        tracker = DeliberationTracker(input_ttl=1, session_ttl=1)
        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-old",
                type="query",
                text="old",
                source="cstp:queryDecisions",
                timestamp=time.time() - 2,  # 2 seconds ago, TTL is 1
                raw_data={},
            ),
        )

        # Manually set last_activity to the past so cleanup sees it as expired
        tracker._sessions["agent:test"].last_activity = time.time() - 2

        # Session is expired
        removed = tracker.cleanup_expired()
        assert removed == 1

        # Nothing to consume
        delib = tracker.consume("agent:test")
        assert delib is None

    def test_auto_steps_generated(self):
        tracker = DeliberationTracker(input_ttl=60)
        now = time.time()

        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-1",
                type="query",
                text="Queried 'topic': 5 results",
                source="cstp:queryDecisions",
                timestamp=now,
                raw_data={},
            ),
        )
        tracker.track(
            "agent:test",
            TrackedInput(
                id="g-1",
                type="guardrail",
                text="Checked 'deploy': allowed",
                source="cstp:checkGuardrails",
                timestamp=now + 1,
                raw_data={},
            ),
        )

        delib = tracker.consume("agent:test")
        assert delib is not None

        # 2 inputs, 2 steps
        assert len(delib.inputs) == 2
        assert len(delib.steps) == 2

        # Steps reference correct inputs
        assert delib.steps[0].inputs_used == ["q-1"]
        assert delib.steps[0].type == "analysis"
        assert delib.steps[1].inputs_used == ["g-1"]
        assert delib.steps[1].type == "constraint"

        # Total duration calculated
        assert delib.total_duration_ms is not None
        assert delib.total_duration_ms >= 900  # ~1000ms

    def test_no_deliberation_when_empty(self):
        tracker = DeliberationTracker(input_ttl=60)
        delib = tracker.consume("agent:nobody")
        assert delib is None

    def test_single_input_no_duration(self):
        tracker = DeliberationTracker(input_ttl=60)
        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-1",
                type="query",
                text="single",
                source="cstp:queryDecisions",
                timestamp=time.time(),
                raw_data={},
            ),
        )

        delib = tracker.consume("agent:test")
        assert delib is not None
        assert delib.total_duration_ms is None  # Can't calc from 1 input

    def test_session_count(self):
        tracker = DeliberationTracker(input_ttl=60)
        assert tracker.session_count == 0

        tracker.track(
            "a",
            TrackedInput(
                id="q-1", type="query", text="", source="",
                timestamp=time.time(), raw_data={},
            ),
        )
        tracker.track(
            "b",
            TrackedInput(
                id="q-2", type="query", text="", source="",
                timestamp=time.time(), raw_data={},
            ),
        )
        assert tracker.session_count == 2

        tracker.consume("a")
        assert tracker.session_count == 1

    def test_get_inputs_peek(self):
        tracker = DeliberationTracker(input_ttl=60)
        tracker.track(
            "agent:test",
            TrackedInput(
                id="q-1", type="query", text="test", source="",
                timestamp=time.time(), raw_data={},
            ),
        )

        # Peek doesn't consume
        inputs = tracker.get_inputs("agent:test")
        assert len(inputs) == 1

        # Still available for consume
        delib = tracker.consume("agent:test")
        assert delib is not None


class TestAutoAttachDeliberation:
    """Tests for the auto_attach_deliberation merge logic."""

    def setup_method(self):
        reset_tracker()

    def test_no_tracking_no_explicit(self):
        result, auto = auto_attach_deliberation("rpc:test", None)
        assert result is None
        assert auto is False

    def test_auto_only(self):
        track_query(
            key="rpc:test",
            query="test query",
            result_count=3,
            top_ids=["a", "b", "c"],
            retrieval_mode="semantic",
        )

        result, auto = auto_attach_deliberation("rpc:test", None)
        assert result is not None
        assert auto is True
        assert len(result.inputs) == 1
        assert result.inputs[0].source == "cstp:queryDecisions"

    def test_explicit_only(self):
        explicit = Deliberation(
            inputs=[DeliberationInput(id="manual", text="manual input")],
            steps=[DeliberationStep(step=1, thought="manual step")],
        )

        result, auto = auto_attach_deliberation("rpc:test", explicit)
        assert result is not None
        assert auto is False
        assert len(result.inputs) == 1
        assert result.inputs[0].id == "manual"

    def test_merge_tracked_into_explicit(self):
        # Track a query
        track_query(
            key="rpc:test",
            query="topic",
            result_count=2,
            top_ids=["x"],
            retrieval_mode="hybrid",
        )

        # Provide explicit deliberation
        explicit = Deliberation(
            inputs=[DeliberationInput(id="manual", text="manual input")],
            steps=[DeliberationStep(step=1, thought="manual step")],
        )

        result, auto = auto_attach_deliberation("rpc:test", explicit)
        assert result is not None
        assert auto is True
        # Should have both: manual + auto-tracked inputs
        assert len(result.inputs) == 2
        ids = {i.id for i in result.inputs}
        assert "manual" in ids
        # Should also have merged steps (manual step + auto step)
        assert len(result.steps) >= 2
        # Auto step should be renumbered after manual step
        assert result.steps[-1].step > 1

    def test_no_duplicate_merge(self):
        """Tracked inputs with same ID shouldn't be duplicated."""
        tracker = get_tracker()
        tracker.track(
            "rpc:test",
            TrackedInput(
                id="shared-id",
                type="query",
                text="test",
                source="cstp:queryDecisions",
                timestamp=time.time(),
                raw_data={},
            ),
        )

        explicit = Deliberation(
            inputs=[DeliberationInput(id="shared-id", text="same input")],
        )

        result, auto = auto_attach_deliberation("rpc:test", explicit)
        assert result is not None
        assert len(result.inputs) == 1  # No duplicate


class TestTrackHelpers:
    """Tests for convenience tracking functions."""

    def setup_method(self):
        reset_tracker()

    def test_track_query(self):
        track_query("rpc:em", "test query", 5, ["a", "b"], "hybrid")
        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:em")
        assert len(inputs) == 1
        assert inputs[0].type == "query"
        assert "test query" in inputs[0].text
        assert inputs[0].raw_data["result_count"] == 5

    def test_track_guardrail(self):
        track_guardrail("rpc:em", "deploy feature", True, 0)
        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:em")
        assert len(inputs) == 1
        assert inputs[0].type == "guardrail"
        assert "allowed" in inputs[0].text

    def test_track_guardrail_blocked(self):
        track_guardrail("rpc:em", "risky action", False, 2)
        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:em")
        assert len(inputs) == 1
        assert "blocked" in inputs[0].text
        assert inputs[0].raw_data["violation_count"] == 2

    def test_track_lookup(self):
        track_lookup("rpc:em", "abc123", "My Decision")
        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:em")
        assert len(inputs) == 1
        assert inputs[0].type == "lookup"
        assert "abc123" in inputs[0].text

    def test_track_stats(self):
        track_stats("rpc:em", 50, 6, 1.85)
        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:em")
        assert len(inputs) == 1
        assert inputs[0].type == "stats"
        assert inputs[0].raw_data["total_decisions"] == 50
