"""Embedding provider abstraction layer for CSTP.

Defines the EmbeddingProvider ABC that all embedding backends
(Gemini, OpenAI, Ollama, etc.) must implement.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding generation interface.

    All embedding providers implement this interface. Services call
    embed() to generate vectors without knowing the underlying model.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text.

        Implementations should truncate text exceeding max_length internally.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            RuntimeError: If embedding generation fails.
        """
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Default implementation calls embed() sequentially.
        Providers with batch APIs should override for efficiency.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors, one per input text.
        """
        return [await self.embed(t) for t in texts]

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector dimensionality."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @property
    def max_length(self) -> int:
        """Maximum input text length in characters. Default 8000."""
        return 8000
