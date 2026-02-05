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

    indexed = await index_to_chromadb(decision_id, embedding_text, metadata)

    return RecordDecisionResponse(
        success=True,
        id=decision_id,
        path=file_path,
        indexed=indexed,
        timestamp=now.isoformat(),
    )
