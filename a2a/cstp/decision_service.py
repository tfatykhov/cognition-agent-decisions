"""Decision recording service for CSTP.

Creates decision YAML files and indexes them to ChromaDB.
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import httpx
import yaml

# Environment configuration
DECISIONS_PATH = os.getenv("DECISIONS_PATH", "decisions")
CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "decisions_gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-004"

logger = logging.getLogger(__name__)


@dataclass
class Reason:
    """A reason supporting a decision."""

    type: str  # authority, analogy, analysis, pattern, intuition
    text: str
    strength: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML."""
        return {
            "type": self.type,
            "text": self.text,
            "strength": self.strength,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Reason":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "analysis"),
            text=data.get("text", ""),
            strength=float(data.get("strength", 0.8)),
        )


@dataclass
class PreDecisionProtocol:
    """Pre-decision protocol tracking."""

    query_run: bool = False
    similar_found: int = 0
    guardrails_checked: bool = False
    guardrails_passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML."""
        return {
            "query_run": self.query_run,
            "similar_found": self.similar_found,
            "guardrails_checked": self.guardrails_checked,
            "guardrails_passed": self.guardrails_passed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreDecisionProtocol":
        """Create from dictionary."""
        return cls(
            query_run=bool(data.get("query_run", data.get("queryRun", False))),
            similar_found=int(data.get("similar_found", data.get("similarFound", 0))),
            guardrails_checked=bool(
                data.get("guardrails_checked", data.get("guardrailsChecked", False))
            ),
            guardrails_passed=bool(
                data.get("guardrails_passed", data.get("guardrailsPassed", False))
            ),
        )


@dataclass
class ProjectContext:
    """Project context for a decision."""

    project: str | None = None  # owner/repo format
    feature: str | None = None  # Feature or epic name
    pr: int | None = None  # PR number
    file: str | None = None  # File path relative to repo root
    line: int | None = None  # Line number in file
    commit: str | None = None  # Commit SHA (7+ chars)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectContext":
        """Create from dictionary."""
        return cls(
            project=data.get("project"),
            feature=data.get("feature"),
            pr=data.get("pr"),
            file=data.get("file"),
            line=data.get("line"),
            commit=data.get("commit"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {}
        if self.project:
            result["project"] = self.project
        if self.feature:
            result["feature"] = self.feature
        if self.pr is not None:
            result["pr"] = self.pr
        if self.file:
            result["file"] = self.file
        if self.line is not None:
            result["line"] = self.line
        if self.commit:
            result["commit"] = self.commit
        return result

    def has_any(self) -> bool:
        """Check if any project context is set."""
        return any([
            self.project,
            self.feature,
            self.pr is not None,
            self.file,
            self.line is not None,
            self.commit,
        ])


@dataclass
class RecordDecisionRequest:
    """Request to record a new decision."""

    decision: str
    confidence: float
    category: str
    stakes: str = "medium"
    context: str | None = None
    reasons: list[Reason] = field(default_factory=list)
    kpi_indicators: list[str] = field(default_factory=list)
    mental_state: str | None = None
    review_in: str | None = None
    tags: list[str] = field(default_factory=list)
    pre_decision: PreDecisionProtocol | None = None
    project_context: ProjectContext | None = None  # F010: Project context
    agent_id: str | None = None  # Set from auth

    @classmethod
    def from_dict(cls, data: dict[str, Any], agent_id: str | None = None) -> "RecordDecisionRequest":
        """Create from dictionary (JSON-RPC params)."""
        reasons = [
            Reason.from_dict(r) if isinstance(r, dict) else r
            for r in data.get("reasons", [])
        ]

        pre_decision = None
        if "preDecision" in data or "pre_decision" in data:
            pd_data = data.get("preDecision", data.get("pre_decision", {}))
            pre_decision = PreDecisionProtocol.from_dict(pd_data)

        # F010: Parse project context fields
        project_context = None
        project_fields = ["project", "feature", "pr", "file", "line", "commit"]
        if any(data.get(f) is not None for f in project_fields):
            project_context = ProjectContext.from_dict(data)

        return cls(
            decision=data.get("decision", ""),
            confidence=float(data.get("confidence", 0.5)),
            category=data.get("category", "process"),
            stakes=data.get("stakes", "medium"),
            context=data.get("context"),
            reasons=reasons,
            kpi_indicators=data.get("kpiIndicators", data.get("kpi_indicators", [])),
            mental_state=data.get("mentalState", data.get("mental_state")),
            review_in=data.get("reviewIn", data.get("review_in")),
            tags=data.get("tags", []),
            pre_decision=pre_decision,
            project_context=project_context,
            agent_id=agent_id,
        )

    def validate(self) -> list[str]:
        """Validate the request. Returns list of errors."""
        errors = []

        if not self.decision or not self.decision.strip():
            errors.append("decision: required field")

        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence: must be between 0.0 and 1.0")

        valid_categories = {"architecture", "process", "integration", "tooling", "security"}
        if self.category not in valid_categories:
            errors.append(f"category: must be one of {valid_categories}")

        valid_stakes = {"low", "medium", "high", "critical"}
        if self.stakes not in valid_stakes:
            errors.append(f"stakes: must be one of {valid_stakes}")

        valid_reason_types = {"authority", "analogy", "analysis", "pattern", "intuition"}
        for i, reason in enumerate(self.reasons):
            if reason.type not in valid_reason_types:
                errors.append(f"reasons[{i}].type: must be one of {valid_reason_types}")
            if not reason.text:
                errors.append(f"reasons[{i}].text: required")

        valid_mental_states = {"deliberate", "reactive", "exploratory", "habitual", "pressured"}
        if self.mental_state and self.mental_state not in valid_mental_states:
            errors.append(f"mentalState: must be one of {valid_mental_states}")

        return errors


@dataclass
class RecordDecisionResponse:
    """Response from recording a decision."""

    success: bool
    id: str
    path: str
    indexed: bool
    timestamp: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON-RPC response."""
        result: dict[str, Any] = {
            "success": self.success,
            "id": self.id,
            "path": self.path,
            "indexed": self.indexed,
            "timestamp": self.timestamp,
        }
        if self.error:
            result["error"] = self.error
        return result


def generate_decision_id() -> str:
    """Generate a short unique decision ID."""
    return uuid.uuid4().hex[:8]


def calculate_review_date(review_in: str | None) -> str | None:
    """Calculate review date from relative string like '7d', '2w', '1m'."""
    if not review_in:
        return None

    now = datetime.now(UTC)
    value = int(review_in[:-1])
    unit = review_in[-1].lower()

    if unit == "d":
        days = value
    elif unit == "w":
        days = value * 7
    elif unit == "m":
        days = value * 30
    else:
        return None

    from datetime import timedelta
    review_date = now + timedelta(days=days)
    return review_date.strftime("%Y-%m-%d")


def build_decision_yaml(request: RecordDecisionRequest, decision_id: str) -> dict[str, Any]:
    """Build the decision YAML structure."""
    now = datetime.now(UTC)

    decision_data: dict[str, Any] = {
        "id": decision_id,
        "summary": request.decision,
        "decision": request.decision,  # Alias for compatibility
        "category": request.category,
        "confidence": request.confidence,
        "stakes": request.stakes,
        "status": "pending",
        "date": now.isoformat(),
    }

    if request.context:
        decision_data["context"] = request.context

    if request.reasons:
        decision_data["reasons"] = [r.to_dict() for r in request.reasons]

    if request.kpi_indicators:
        decision_data["kpi_indicators"] = request.kpi_indicators

    if request.mental_state:
        decision_data["mental_state"] = request.mental_state

    if request.review_in:
        review_date = calculate_review_date(request.review_in)
        if review_date:
            decision_data["review_by"] = review_date

    if request.tags:
        decision_data["tags"] = request.tags

    if request.pre_decision:
        decision_data["pre_decision"] = request.pre_decision.to_dict()

    if request.agent_id:
        decision_data["recorded_by"] = request.agent_id

    # F010: Add project context fields
    if request.project_context and request.project_context.has_any():
        pc = request.project_context
        if pc.project:
            decision_data["project"] = pc.project
        if pc.feature:
            decision_data["feature"] = pc.feature
        if pc.pr is not None:
            decision_data["pr"] = pc.pr
        if pc.file:
            decision_data["file"] = pc.file
        if pc.line is not None:
            decision_data["line"] = pc.line
        if pc.commit:
            decision_data["commit"] = pc.commit

    return decision_data


def write_decision_file(
    decision_data: dict[str, Any],
    decision_id: str,
    base_path: str | None = None,
) -> str:
    """Write decision to YAML file. Returns file path."""
    base = Path(base_path or DECISIONS_PATH)
    now = datetime.now(UTC)

    # Create directory structure: decisions/YYYY/MM/
    year_month_dir = base / str(now.year) / f"{now.month:02d}"
    year_month_dir.mkdir(parents=True, exist_ok=True)

    # File name: YYYY-MM-DD-decision-<id>.yaml
    filename = f"{now.strftime('%Y-%m-%d')}-decision-{decision_id}.yaml"
    file_path = year_month_dir / filename

    with open(file_path, "w") as f:
        yaml.dump(decision_data, f, default_flow_style=False, sort_keys=False)

    return str(file_path)


async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding using Gemini API."""
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                url,
                headers={"x-goog-api-key": GEMINI_API_KEY},
                json={
                    "model": f"models/{EMBEDDING_MODEL}",
                    "content": {"parts": [{"text": text}]},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", {}).get("values", [])
        except Exception as e:
            logger.warning("Failed to generate embedding: %s", e)
            return None


def build_embedding_text(request: RecordDecisionRequest) -> str:
    """Build text for embedding generation."""
    parts = [f"Decision: {request.decision}"]

    if request.context:
        parts.append(f"Context: {request.context}")

    parts.append(f"Category: {request.category}")

    if request.reasons:
        reasons_text = " | ".join(r.text for r in request.reasons)
        parts.append(f"Reasons: {reasons_text}")

    if request.tags:
        parts.append(f"Tags: {', '.join(request.tags)}")

    # F010: Include project context in embedding text
    if request.project_context:
        pc = request.project_context
        if pc.project:
            parts.append(f"Project: {pc.project}")
        if pc.feature:
            parts.append(f"Feature: {pc.feature}")
        if pc.file:
            parts.append(f"File: {pc.file}")

    return "\n".join(parts)


async def index_to_chromadb(
    decision_id: str,
    embedding_text: str,
    metadata: dict[str, Any],
    embedding: list[float] | None = None,
) -> bool:
    """Index decision to ChromaDB. Returns success status."""
    # Generate embedding if not provided
    if embedding is None:
        embedding = await generate_embedding(embedding_text)

    if embedding is None:
        return False

    # Upsert to ChromaDB via HTTP API
    url = f"{CHROMA_URL}/api/v1/collections/{CHROMA_COLLECTION}/upsert"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                url,
                json={
                    "ids": [decision_id],
                    "documents": [embedding_text],
                    "metadatas": [metadata],
                    "embeddings": [embedding],
                },
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning("ChromaDB upsert failed, trying add: %s", e)
            # Try alternative: add instead of upsert
            try:
                add_url = f"{CHROMA_URL}/api/v1/collections/{CHROMA_COLLECTION}/add"
                response = await client.post(
                    add_url,
                    json={
                        "ids": [decision_id],
                        "documents": [embedding_text],
                        "metadatas": [metadata],
                        "embeddings": [embedding],
                    },
                )
                response.raise_for_status()
                return True
            except Exception as add_e:
                logger.error("ChromaDB indexing failed: %s", add_e)
                return False


async def record_decision(
    request: RecordDecisionRequest,
    decisions_path: str | None = None,
) -> RecordDecisionResponse:
    """Record a new decision.

    Creates YAML file and indexes to ChromaDB.

    Args:
        request: The decision to record.
        decisions_path: Override for decisions directory.

    Returns:
        Response with decision ID and status.
    """
    now = datetime.now(UTC)
    decision_id = generate_decision_id()

    # Build and write YAML
    decision_data = build_decision_yaml(request, decision_id)

    try:
        file_path = write_decision_file(decision_data, decision_id, decisions_path)
    except Exception as e:
        return RecordDecisionResponse(
            success=False,
            id=decision_id,
            path="",
            indexed=False,
            timestamp=now.isoformat(),
            error=f"Failed to write decision file: {e}",
        )

    # Index to ChromaDB
    embedding_text = build_embedding_text(request)
    metadata = {
        "path": file_path,
        "category": request.category,
        "stakes": request.stakes,
        "confidence": request.confidence,
        "date": now.strftime("%Y-%m-%d"),
    }
    if request.agent_id:
        metadata["agent"] = request.agent_id

    # F010: Add project context to ChromaDB metadata
    if request.project_context:
        pc = request.project_context
        if pc.project:
            metadata["project"] = pc.project
        if pc.feature:
            metadata["feature"] = pc.feature
        if pc.pr is not None:
            metadata["pr"] = pc.pr
        if pc.file:
            metadata["file"] = pc.file

    indexed = await index_to_chromadb(decision_id, embedding_text, metadata)

    return RecordDecisionResponse(
        success=True,
        id=decision_id,
        path=file_path,
        indexed=indexed,
        timestamp=now.isoformat(),
    )


# =============================================================================
# Review Decision
# =============================================================================


@dataclass
class ReviewDecisionRequest:
    """Request to review an existing decision with outcome data."""

    id: str
    outcome: str  # success, partial, failure, abandoned
    actual_result: str | None = None
    lessons: str | None = None
    notes: str | None = None
    affected_kpis: dict[str, float] | None = None
    reviewer_id: str | None = None  # Set from auth

    @classmethod
    def from_dict(cls, data: dict[str, Any], reviewer_id: str | None = None) -> "ReviewDecisionRequest":
        """Create from dictionary (JSON-RPC params)."""
        return cls(
            id=data.get("id", ""),
            outcome=data.get("outcome", ""),
            actual_result=data.get("actualResult", data.get("actual_result")),
            lessons=data.get("lessons"),
            notes=data.get("notes"),
            affected_kpis=data.get("affectedKpis", data.get("affected_kpis")),
            reviewer_id=reviewer_id,
        )

    def validate(self) -> list[str]:
        """Validate the request. Returns list of errors."""
        errors = []

        if not self.id or not self.id.strip():
            errors.append("id: required field")

        valid_outcomes = {"success", "partial", "failure", "abandoned"}
        if self.outcome not in valid_outcomes:
            errors.append(f"outcome: must be one of {valid_outcomes}")

        return errors


@dataclass
class ReviewDecisionResponse:
    """Response from reviewing a decision."""

    success: bool
    id: str
    path: str
    status: str
    reviewed_at: str
    reindexed: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON-RPC response."""
        result: dict[str, Any] = {
            "success": self.success,
            "id": self.id,
            "path": self.path,
            "status": self.status,
            "reviewedAt": self.reviewed_at,
            "reindexed": self.reindexed,
        }
        if self.error:
            result["error"] = self.error
        return result


async def find_decision(
    decision_id: str,
    decisions_path: str | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    """Find a decision by ID.

    Searches decisions directory for matching ID.

    Args:
        decision_id: The decision ID to find (must be alphanumeric).
        decisions_path: Override for decisions directory.

    Returns:
        Tuple of (path, data) or None if not found.

    Raises:
        ValueError: If decision_id contains invalid characters.
    """
    # Validate decision_id to prevent path traversal
    if not decision_id or not decision_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"Invalid decision ID format: {decision_id}")
    base = Path(decisions_path or DECISIONS_PATH)

    if not base.exists():
        return None

    # Search pattern: decisions/YYYY/MM/*-decision-{id}.yaml
    for yaml_file in base.rglob(f"*-decision-{decision_id}.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            return (yaml_file, data)
        except Exception as e:
            logger.warning("Failed to read decision file %s: %s", yaml_file, e)

    return None


async def reindex_decision(
    decision_id: str,
    data: dict[str, Any],
    file_path: str,
) -> bool:
    """Re-index a decision with updated metadata.

    Args:
        decision_id: The decision ID.
        data: The updated decision data.
        file_path: Path to the decision file.

    Returns:
        True if indexing succeeded.
    """
    # Build embedding text from decision data
    parts = [f"Decision: {data.get('summary', data.get('decision', ''))}"]

    if data.get("context"):
        parts.append(f"Context: {data['context']}")

    parts.append(f"Category: {data.get('category', 'unknown')}")

    if data.get("reasons"):
        reasons_text = " | ".join(
            r.get("text", "") for r in data["reasons"] if isinstance(r, dict)
        )
        if reasons_text:
            parts.append(f"Reasons: {reasons_text}")

    # Add outcome for reviewed decisions
    if data.get("outcome"):
        parts.append(f"Outcome: {data['outcome']}")

    if data.get("lessons"):
        parts.append(f"Lessons: {data['lessons']}")

    embedding_text = "\n".join(parts)

    # Build metadata
    metadata: dict[str, Any] = {
        "path": file_path,
        "category": data.get("category", "unknown"),
        "stakes": data.get("stakes", "medium"),
        "confidence": data.get("confidence", 0.5),
        "date": data.get("date", "")[:10] if data.get("date") else "",
        "status": data.get("status", "pending"),
    }

    if data.get("outcome"):
        metadata["outcome"] = data["outcome"]

    if data.get("recorded_by"):
        metadata["agent"] = data["recorded_by"]

    return await index_to_chromadb(decision_id, embedding_text, metadata)


async def review_decision(
    request: ReviewDecisionRequest,
    decisions_path: str | None = None,
) -> ReviewDecisionResponse:
    """Add outcome data to an existing decision.

    Args:
        request: The review data.
        decisions_path: Override for decisions directory.

    Returns:
        Response with review status.
    """
    now = datetime.now(UTC)

    # Find decision
    result = await find_decision(request.id, decisions_path)
    if not result:
        return ReviewDecisionResponse(
            success=False,
            id=request.id,
            path="",
            status="not_found",
            reviewed_at=now.isoformat(),
            reindexed=False,
            error=f"Decision not found: {request.id}",
        )

    path, data = result

    # Update decision data
    data["status"] = "reviewed"
    data["outcome"] = request.outcome
    data["reviewed_at"] = now.isoformat()

    if request.actual_result:
        data["actual_result"] = request.actual_result

    if request.lessons:
        data["lessons"] = request.lessons

    if request.notes:
        data["review_notes"] = request.notes

    if request.affected_kpis:
        data["affected_kpis"] = request.affected_kpis

    if request.reviewer_id:
        data["reviewed_by"] = request.reviewer_id

    # Write updated YAML atomically (write to temp, then replace)
    try:
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            dir=path.parent,
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception as e:
        return ReviewDecisionResponse(
            success=False,
            id=request.id,
            path=str(path),
            status="write_failed",
            reviewed_at=now.isoformat(),
            reindexed=False,
            error=f"Failed to write updated decision: {e}",
        )

    # Re-index with outcome metadata
    reindexed = await reindex_decision(request.id, data, str(path))

    return ReviewDecisionResponse(
        success=True,
        id=request.id,
        path=str(path),
        status="reviewed",
        reviewed_at=now.isoformat(),
        reindexed=reindexed,
    )
