"""Gemini embedding provider for CSTP.

Extracts and unifies the embedding generation logic previously
duplicated in query_service.py and decision_service.py.
"""

import logging
import os
from pathlib import Path

from . import EmbeddingProvider

logger = logging.getLogger(__name__)

# Configurable secrets paths (can be overridden via env)
_SECRETS_PATHS = os.getenv(
    "SECRETS_PATHS",
    "/home/node/.openclaw/workspace/.secrets:~/.secrets",
).split(":")

_cached_api_key: str = ""


def _get_secrets_paths() -> list[Path]:
    """Get list of paths to search for secrets."""
    paths = []
    for p in _SECRETS_PATHS:
        expanded = Path(p.strip()).expanduser()
        paths.append(expanded)
    return paths


def _load_gemini_key() -> str:
    """Load Gemini API key from env or secrets files."""
    global _cached_api_key
    if _cached_api_key:
        return _cached_api_key

    env_key = os.getenv("GEMINI_API_KEY", "")
    if env_key:
        _cached_api_key = env_key
        return _cached_api_key

    for path in _get_secrets_paths():
        gemini_env = path / "gemini.env"
        if gemini_env.exists():
            for line in gemini_env.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    _cached_api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return _cached_api_key

    raise ValueError("GEMINI_API_KEY not found in environment or secrets paths")


class GeminiEmbeddings(EmbeddingProvider):
    """Gemini embedding provider using the Google AI API.

    Uses the x-goog-api-key header (not URL query param) for security.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-embedding-001",
    ) -> None:
        self._api_key = api_key or _load_gemini_key()
        self._model = model
        self._url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:embedContent"
        )

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using Gemini API."""
        import httpx

        if len(text) > self.max_length:
            text = text[: self.max_length]

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        data = {"content": {"parts": [{"text": text}]}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self._url, json=data, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Embedding API error: {response.json()}")
            return response.json()["embedding"]["values"]

    @property
    def dimensions(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return self._model
