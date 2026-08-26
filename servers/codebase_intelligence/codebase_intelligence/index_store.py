from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from codebase_intelligence.chunking import FileChunk
from codebase_intelligence.config import CHROMA_DIR

COLLECTION_NAME = "code_chunks"


@dataclass
class SearchHit:
    file: str
    chunk_index: int
    text: str
    distance: float


class IndexStore(Protocol):
    def index_repo(
        self, repo_id: str, chunks: list[FileChunk], embeddings: list[list[float]]
    ) -> None: ...

    def search(self, repo_id: str, query_embedding: list[float], top_k: int) -> list[SearchHit]: ...


class ChromaIndexStore:
    def __init__(self, persist_dir=CHROMA_DIR) -> None:
        import chromadb

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(COLLECTION_NAME)

    def index_repo(
        self, repo_id: str, chunks: list[FileChunk], embeddings: list[list[float]]
    ) -> None:
        # Re-indexing is idempotent: clear this repo's existing chunks first so a second
        # index_repository call reflects the current state of the files, not a stale union.
        self._collection.delete(where={"repo_id": repo_id})
        if not chunks:
            return

        ids = [f"{repo_id}:{c.relative_path}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {"repo_id": repo_id, "file": c.relative_path, "chunk_index": c.chunk_index}
            for c in chunks
        ]
        self._collection.add(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas  # type: ignore[arg-type]
        )

    def search(self, repo_id: str, query_embedding: list[float], top_k: int) -> list[SearchHit]:
        results = self._collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
            where={"repo_id": repo_id},
        )
        hits: list[SearchHit] = []
        ids = results["ids"]
        if not ids or not ids[0]:
            return hits
        documents = results["documents"] or [[]]
        metadatas = results["metadatas"] or [[]]
        distances = results["distances"] or [[]]
        for doc, metadata, distance in zip(documents[0], metadatas[0], distances[0], strict=True):
            hits.append(
                SearchHit(
                    file=str(metadata["file"]),
                    chunk_index=int(metadata["chunk_index"]),  # type: ignore[arg-type]
                    text=doc,
                    distance=distance,
                )
            )
        return hits


@lru_cache
def get_index_store() -> IndexStore:
    return ChromaIndexStore()
