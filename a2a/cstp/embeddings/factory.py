"""Factory for embedding providers.

Provides singleton management and test injection for EmbeddingProvider instances.
"""

import os

from . import EmbeddingProvider

_provider: EmbeddingProvider | None = None


def create_embedding_provider() -> EmbeddingProvider:
    """Create an EmbeddingProvider based on EMBEDDING_PROVIDER env var.

    Supported values:
        - "gemini" (default): Google Gemini embedding API.
    """
    provider_name = os.getenv("EMBEDDING_PROVIDER", "gemini")
    match provider_name:
        case "gemini":
            from .gemini import GeminiEmbeddings

            return GeminiEmbeddings()
        case _:
            msg = f"Unknown embedding provider: {provider_name}"
            raise ValueError(msg)


def get_embedding_provider() -> EmbeddingProvider:
    """Get or create the singleton EmbeddingProvider."""
    global _provider
    if _provider is None:
        _provider = create_embedding_provider()
    return _provider


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Set the EmbeddingProvider instance (for testing)."""
    global _provider
    _provider = provider
