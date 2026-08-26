import os
from functools import lru_cache
from typing import Protocol

from codebase_intelligence.config import EMBEDDING_MODEL_NAME


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Local embedding model -- no external API key required. Same choice as docuchat-ai's
    ingestion pipeline, applied to code chunks instead of document chunks."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, convert_to_numpy=True).tolist()


class DeterministicFakeEmbedder:
    """Cheap, dependency-free stand-in for the real model. Used only when
    CODEBASE_INTELLIGENCE_FAKE_EMBEDDER is set -- lets the true end-to-end test spawn a real
    server subprocess and exercise the full MCP tool-call wiring without downloading or running
    the ~90MB sentence-transformers model in CI."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), float(text.count(" "))] for text in texts]


@lru_cache
def get_embedder() -> Embedder:
    if os.environ.get("CODEBASE_INTELLIGENCE_FAKE_EMBEDDER"):
        return DeterministicFakeEmbedder()
    return SentenceTransformerEmbedder(EMBEDDING_MODEL_NAME)
