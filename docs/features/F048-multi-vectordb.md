# F048: Multi-Vector-DB Support

**Status:** Proposed
**Priority:** High
**Category:** Infrastructure

## Problem

CSTP is hardcoded to ChromaDB via direct HTTP API calls in `query_service.py` and `decision_service.py`. This creates:

- **Vendor lock-in:** Users must run ChromaDB even if they already have another vector DB
- **No testing without Docker:** No in-memory backend for unit tests
- **Manual hybrid search:** CSTP implements hybrid retrieval (F017) in Python by combining semantic + keyword results, when some backends (Weaviate, Qdrant) support this natively
- **Embedding coupling:** Embedding generation (currently Gemini) is interleaved with storage logic

## Solution

Extract vector operations behind a `VectorStore` abstract interface with pluggable backends, and similarly abstract embedding generation behind an `EmbeddingProvider` interface.

### Architecture

```
┌─────────────────────────────────────────────┐
│              CSTP Services                   │
│  query_service.py  decision_service.py       │
├─────────────────────────────────────────────┤
│           VectorStore Interface              │
│  upsert() query() delete() count() reset()  │
├──────┬──────┬──────┬──────┬──────┬──────────┤
│Chroma│Weavi-│pgvec-│Qdrant│Pine- │ Memory   │
│  DB  │ ate  │ tor  │      │ cone │ (test)   │
└──────┴──────┴──────┴──────┴──────┴──────────┘

┌─────────────────────────────────────────────┐
│         EmbeddingProvider Interface          │
│  embed(texts) -> list[list[float]]          │
├──────┬──────┬──────┬────────────────────────┤
│Gemini│OpenAI│Ollama│sentence-transformers   │
└──────┴──────┴──────┴────────────────────────┘
```

### VectorStore Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(slots=True)
class VectorResult:
    """Single result from vector similarity search."""
    id: str
    document: str
    metadata: dict[str, Any]
    distance: float

class VectorStore(ABC):
    """Abstract vector store interface for decision storage and retrieval."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection, create collection if needed."""
        ...

    @abstractmethod
    async def upsert(
        self,
        id: str,
        document: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> bool:
        """Insert or update a document with its embedding and metadata."""
        ...

    @abstractmethod
    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        """Find similar documents by embedding vector.
        
        Args:
            embedding: Query vector.
            n_results: Maximum results.
            where: Metadata filters (backend translates to native syntax).
        """
        ...

    @abstractmethod
    async def hybrid_query(
        self,
        text: str,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        semantic_weight: float = 0.7,
    ) -> list[VectorResult]:
        """Hybrid search combining semantic + keyword.
        
        Backends with native hybrid (Weaviate, Qdrant) use it directly.
        Others fall back to manual merge.
        """
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> bool:
        """Delete documents by ID."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return total document count."""
        ...

    @abstractmethod
    async def reset(self) -> bool:
        """Delete and recreate the collection."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up connections."""
        ...
```

### EmbeddingProvider Interface

```python
class EmbeddingProvider(ABC):
    """Abstract embedding generation interface."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for one or more texts.
        
        Args:
            texts: Input texts to embed.
            
        Returns:
            List of embedding vectors (one per input text).
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensionality."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...
```

### Backend Implementations

#### ChromaDB (P0 - extract existing)

Move current `query_service.py` and `decision_service.py` HTTP calls into `vectordb/chromadb.py`. Zero behavior change, pure refactor.

```python
class ChromaDBStore(VectorStore):
    """ChromaDB via HTTP API (v2)."""
    
    def __init__(self, url: str, collection: str, tenant: str, database: str):
        self.url = url
        self.collection = collection
        # ... existing HTTP logic moved here

    async def hybrid_query(self, text, embedding, n_results, where, semantic_weight):
        # Manual merge (current F017 implementation)
        semantic = await self.query(embedding, n_results * 2, where)
        keyword = await self._keyword_search(text, n_results * 2, where)
        return self._merge_results(semantic, keyword, semantic_weight)
```

#### Weaviate (P1)

Native hybrid search, built-in vectorization, multi-tenancy.

```python
class WeaviateStore(VectorStore):
    """Weaviate via REST/GraphQL API."""

    def __init__(self, url: str, collection: str, api_key: str | None = None):
        self.url = url
        self.collection = collection
        self.api_key = api_key

    async def query(self, embedding, n_results, where):
        # nearVector query
        payload = {
            "nearVector": {"vector": embedding},
            "limit": n_results,
        }
        if where:
            payload["where"] = self._translate_where(where)
        # ... GraphQL or REST v2 API call

    async def hybrid_query(self, text, embedding, n_results, where, semantic_weight):
        # Native hybrid - single API call
        payload = {
            "hybrid": {
                "query": text,
                "vector": embedding,
                "alpha": semantic_weight,  # 0=BM25, 1=vector
            },
            "limit": n_results,
        }
        if where:
            payload["where"] = self._translate_where(where)
        # ... single request, Weaviate handles fusion internally
```

**Weaviate advantages for CSTP:**
- `hybrid_query` is a single API call (vs ChromaDB's manual 2-query merge)
- `alpha` parameter maps directly to CSTP's `hybrid_weight` config
- Multi-tenancy maps to per-agent isolation (F038 federation)
- Built-in `text2vec-*` modules can replace external embedding providers
- Batch import API for efficient reindexing
- Cross-reference properties could support F045 (graph edges)

**Filter translation:**
```python
def _translate_where(self, cstp_where: dict) -> dict:
    """Translate CSTP where clause to Weaviate filter format."""
    # CSTP: {"category": "architecture", "stakes": {"$in": ["high", "medium"]}}
    # Weaviate: {"operator": "And", "operands": [
    #   {"path": ["category"], "operator": "Equal", "valueText": "architecture"},
    #   {"path": ["stakes"], "operator": "ContainsAny", "valueTextArray": ["high", "medium"]}
    # ]}
```

#### pgvector (P1)

PostgreSQL with pgvector extension. Zero extra infrastructure for Postgres users.

```python
class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector extension."""

    def __init__(self, dsn: str, table: str = "decisions"):
        self.dsn = dsn
        self.table = table

    async def query(self, embedding, n_results, where):
        # SQL with cosine distance
        sql = f"""
            SELECT id, document, metadata, 
                   1 - (embedding <=> $1::vector) as similarity
            FROM {self.table}
            WHERE {self._build_where(where)}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

    async def hybrid_query(self, text, embedding, n_results, where, semantic_weight):
        # pg_trgm for keyword + pgvector for semantic
        sql = f"""
            WITH semantic AS (
                SELECT id, document, metadata,
                       1 - (embedding <=> $1::vector) as score
                FROM {self.table} WHERE {self._build_where(where)}
                ORDER BY embedding <=> $1::vector LIMIT $3
            ),
            keyword AS (
                SELECT id, document, metadata,
                       ts_rank(to_tsvector(document), plainto_tsquery($2)) as score
                FROM {self.table} WHERE {self._build_where(where)}
                ORDER BY score DESC LIMIT $3
            )
            SELECT id, document, metadata,
                   ({semantic_weight} * COALESCE(s.score, 0) + 
                    {1 - semantic_weight} * COALESCE(k.score, 0)) as combined
            FROM semantic s FULL OUTER JOIN keyword k USING (id)
            ORDER BY combined DESC LIMIT $3
        """
```

#### Qdrant (P2)

```python
class QdrantStore(VectorStore):
    """Qdrant via REST API."""

    async def hybrid_query(self, text, embedding, n_results, where, semantic_weight):
        # Qdrant has native hybrid via "fusion" in query API
        payload = {
            "prefetch": [
                {"query": embedding, "using": "dense", "limit": n_results * 2},
                {"query": text, "using": "sparse", "limit": n_results * 2},
            ],
            "query": {"fusion": "rrf"},  # Reciprocal Rank Fusion
            "limit": n_results,
        }
```

#### In-Memory (P1 - testing)

```python
class MemoryStore(VectorStore):
    """In-memory vector store for testing. No external dependencies."""

    def __init__(self):
        self._docs: dict[str, dict] = {}

    async def query(self, embedding, n_results, where):
        # Brute-force cosine similarity
        results = []
        for id, doc in self._docs.items():
            if self._matches_where(doc["metadata"], where):
                dist = self._cosine_distance(embedding, doc["embedding"])
                results.append(VectorResult(id, doc["document"], doc["metadata"], dist))
        results.sort(key=lambda r: r.distance)
        return results[:n_results]
```

### Embedding Providers

```
a2a/cstp/embeddings/
├── __init__.py             # ABC + factory
├── gemini.py               # Current (768 dims, free tier)
├── openai.py               # text-embedding-3-small/large
├── ollama.py               # Local models (nomic-embed-text, etc.)
├── sentence_transformers.py # Local HuggingFace models
└── weaviate_builtin.py     # Weaviate's text2vec modules (no separate call needed)
```

### Configuration

```env
# Vector store
VECTOR_BACKEND=chromadb                    # chromadb | weaviate | pgvector | qdrant | pinecone | memory
VECTOR_URL=http://chromadb:8000            # Backend URL
VECTOR_COLLECTION=decisions                # Collection/table name
VECTOR_API_KEY=                            # For cloud backends (Pinecone, Weaviate Cloud)

# Embeddings
EMBEDDING_PROVIDER=gemini                  # gemini | openai | ollama | sentence_transformers | weaviate
EMBEDDING_MODEL=text-embedding-004         # Provider-specific model name
EMBEDDING_DIMENSIONS=768                   # Output dimensions
EMBEDDING_URL=                             # For Ollama/custom endpoints

# Weaviate-specific
WEAVIATE_TEXT2VEC_MODULE=text2vec-openai   # Built-in vectorizer (optional)
WEAVIATE_MULTI_TENANCY=false              # Enable per-agent tenants
```

### Factory

```python
def create_vector_store() -> VectorStore:
    backend = os.getenv("VECTOR_BACKEND", "chromadb")
    url = os.getenv("VECTOR_URL", "http://chromadb:8000")
    collection = os.getenv("VECTOR_COLLECTION", "decisions")
    api_key = os.getenv("VECTOR_API_KEY")

    match backend:
        case "chromadb":
            return ChromaDBStore(url=url, collection=collection)
        case "weaviate":
            return WeaviateStore(url=url, collection=collection, api_key=api_key)
        case "pgvector":
            return PgVectorStore(dsn=url, table=collection)
        case "qdrant":
            return QdrantStore(url=url, collection=collection, api_key=api_key)
        case "pinecone":
            return PineconeStore(api_key=api_key, index=collection)
        case "memory":
            return MemoryStore()
        case _:
            raise ValueError(f"Unknown vector backend: {backend}")

def create_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-004")

    match provider:
        case "gemini":
            return GeminiEmbeddings(model=model)
        case "openai":
            return OpenAIEmbeddings(model=model)
        case "ollama":
            url = os.getenv("EMBEDDING_URL", "http://localhost:11434")
            return OllamaEmbeddings(url=url, model=model)
        case "weaviate":
            return WeaviateBuiltinEmbeddings()  # No-op, Weaviate handles it
        case _:
            raise ValueError(f"Unknown embedding provider: {provider}")
```

### Docker Compose Examples

**ChromaDB (current, default):**
```yaml
services:
  cstp:
    environment:
      VECTOR_BACKEND: chromadb
      VECTOR_URL: http://chromadb:8000
      EMBEDDING_PROVIDER: gemini
  chromadb:
    image: chromadb/chroma:latest
```

**Weaviate (hybrid search, built-in embeddings):**
```yaml
services:
  cstp:
    environment:
      VECTOR_BACKEND: weaviate
      VECTOR_URL: http://weaviate:8080
      EMBEDDING_PROVIDER: weaviate
      WEAVIATE_TEXT2VEC_MODULE: text2vec-openai
  weaviate:
    image: semitechnologies/weaviate:latest
    environment:
      ENABLE_MODULES: text2vec-openai
      DEFAULT_VECTORIZER_MODULE: text2vec-openai
```

**pgvector (no extra services):**
```yaml
services:
  cstp:
    environment:
      VECTOR_BACKEND: pgvector
      VECTOR_URL: postgresql://user:pass@postgres:5432/cstp
      EMBEDDING_PROVIDER: ollama
      EMBEDDING_URL: http://ollama:11434
  postgres:
    image: pgvector/pgvector:pg16
```

**Fully local (no cloud APIs):**
```yaml
services:
  cstp:
    environment:
      VECTOR_BACKEND: qdrant
      VECTOR_URL: http://qdrant:6333
      EMBEDDING_PROVIDER: ollama
      EMBEDDING_MODEL: nomic-embed-text
  qdrant:
    image: qdrant/qdrant:latest
  ollama:
    image: ollama/ollama:latest
```

## Phases

### P1: Abstraction + ChromaDB extraction
- Define `VectorStore` and `EmbeddingProvider` ABCs
- Extract ChromaDB logic from `query_service.py` and `decision_service.py` into `vectordb/chromadb.py`
- Extract Gemini embedding logic into `embeddings/gemini.py`
- Add `MemoryStore` for testing
- Factory with env-based backend selection
- **Zero behavior change** - existing ChromaDB deployments work unchanged

### P2: Weaviate + pgvector
- Implement `WeaviateStore` with native hybrid search
- Implement `PgVectorStore` with pgvector extension
- Add `OllamaEmbeddings` for fully local stack
- Docker compose examples for each
- Integration tests per backend

### P3: Qdrant + Pinecone + OpenAI embeddings
- Implement remaining backends
- `OpenAIEmbeddings` provider
- Cloud deployment guides

### P4: Backend-specific optimizations
- Weaviate multi-tenancy for agent isolation (F038)
- Weaviate cross-references for decision graph edges (F045)
- pgvector partitioning for large decision sets
- Batch import APIs for efficient reindexing

## Migration Guide

For existing ChromaDB users: **nothing changes.** Set `VECTOR_BACKEND=chromadb` (or leave unset, it's the default).

For new deployments: choose based on your stack:

| Already running | Recommended backend | Why |
|----------------|-------------------|-----|
| Nothing | ChromaDB | Simplest, lightweight |
| PostgreSQL | pgvector | No extra infra |
| Kubernetes | Weaviate or Qdrant | Production-grade, scalable |
| Cloud-only | Pinecone or Weaviate Cloud | Managed, zero-ops |
| Air-gapped / local | Qdrant + Ollama | Fully offline |

## Integration Points

- F002 (Query): `query_service.py` uses `VectorStore.query()` / `hybrid_query()`
- F007 (Record): `decision_service.py` uses `VectorStore.upsert()`
- F017 (Hybrid Retrieval): Backends with native hybrid skip manual merge
- F038 (Federation): Weaviate multi-tenancy for per-agent isolation
- F045 (Graph): Weaviate cross-references for graph edges alongside vectors
- F046 (Pre-Action): Uses query internally, benefits from faster backends
- F047 (Session Context): Bulk query benefits from backend optimizations
