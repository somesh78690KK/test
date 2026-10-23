"""T.A.R.O. - Tier 2 Long-Term Semantic Memory (ChromaDB).

ARCHITECTURE reference: section 12.
MEMORY reference: sections 3 (Tier 2), 12 (Offline Embeddings).
TASKS: TASK-060.

Collections:
- facts: Stable facts the user stated.
- preferences: Preferred assistant behaviors.
- notes: User notes created with notes tool.
- documents: Chunks of indexed local files.

Offline requirement (MEMORY section 12):
Embeddings MUST work with network disabled. This module implements a local
deterministic offline embedding function that never makes network requests.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from core.log.setup import get_logger

logger = get_logger(__name__)


def _offline_embed_text(text: str, dim: int = 384) -> list[float]:
    """Offline, deterministic embedding generator that requires no network.

    Generates a normalized dense vector using character n-grams and hashing.
    Used as an offline-first embedding to ensure ChromaDB never calls remote APIs.
    """
    words = re.findall(r"\w+", text.lower())
    vec = [0.0] * dim
    if not words:
        return vec

    # Combine word and character trigram hashing
    for i, word in enumerate(words):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0 + (1.0 / (i + 1))

        # Add trigrams
        if len(word) >= 3:
            for j in range(len(word) - 2):
                tri = word[j : j + 3]
                h_tri = int(hashlib.sha256(tri.encode()).hexdigest(), 16)
                idx_tri = h_tri % dim
                vec[idx_tri] += 0.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        vec = [x / norm for x in vec]
    return vec


try:
    from chromadb import Documents, EmbeddingFunction, Embeddings
except ImportError:
    # Fallback types if chromadb is not yet installed
    Documents = list[str]  # type: ignore[misc,assignment]
    Embeddings = list[list[float]]  # type: ignore[misc,assignment]

    class EmbeddingFunction:  # type: ignore[no-redef]
        pass


class OfflineEmbeddingFunction(EmbeddingFunction[Documents] if "EmbeddingFunction" in globals() else object):  # type: ignore[misc]
    """ChromaDB-compatible embedding function that works 100% offline."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def name() -> str:
        return "offline_embedding"

    def __call__(self, input: Documents) -> Embeddings:
        return [_offline_embed_text(t) for t in input]


@dataclass
class SemanticRecord:
    id: str
    text: str
    source: str
    created_at: str
    similarity: float = 1.0
    metadata: dict[str, Any] | None = None


class ChromaMemoryStore:
    """Tier 2 semantic memory backed by local persistent ChromaDB."""

    COLLECTIONS = ("facts", "preferences", "notes", "documents")

    def __init__(self, persist_dir: Path | str = "data/chroma") -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_fn = OfflineEmbeddingFunction()
        self._client: Any = None
        self._collections: dict[str, Any] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize Chroma persistent client and collections."""
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            for name in self.COLLECTIONS:
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    embedding_function=self.embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
            logger.info("chroma_memory_initialized", path=str(self.persist_dir))
        except Exception as e:
            logger.warning("chroma_init_error", error=str(e))

    def add(
        self,
        collection_name: str,
        text: str,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> str:
        """Add a text record to a collection."""
        if collection_name not in self._collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        rec_id = record_id or f"{collection_name}_{datetime.now(timezone.utc).timestamp():.6f}"
        now_iso = datetime.now(timezone.utc).isoformat()
        meta = metadata.copy() if metadata else {}
        meta["source"] = source
        meta["created_at"] = now_iso

        coll = self._collections[collection_name]
        coll.add(
            ids=[rec_id],
            documents=[text],
            metadatas=[meta],
        )
        logger.info("chroma_record_added", collection=collection_name, id=rec_id)
        return rec_id

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 4,
        min_similarity: float = 0.35,
    ) -> list[SemanticRecord]:
        """Perform semantic search on a collection."""
        if collection_name not in self._collections:
            return []

        coll = self._collections[collection_name]
        count = coll.count()
        if count == 0:
            return []

        actual_n = min(n_results, count)
        results = coll.query(
            query_texts=[query_text],
            n_results=actual_n,
        )

        records: list[SemanticRecord] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, rec_id in enumerate(ids):
            # Cosine distance: distance in [0, 2], similarity = 1 - (distance / 2) or 1 - distance
            dist = distances[i] if i < len(distances) else 1.0
            similarity = max(0.0, 1.0 - dist)
            if similarity < min_similarity:
                continue

            meta = metas[i] if i < len(metas) else {}
            records.append(
                SemanticRecord(
                    id=rec_id,
                    text=docs[i],
                    source=meta.get("source", "unknown"),
                    created_at=meta.get("created_at", ""),
                    similarity=round(similarity, 3),
                    metadata=meta,
                )
            )

        return records

    def delete(self, collection_name: str, record_id: str) -> bool:
        """Delete a record by ID."""
        if collection_name not in self._collections:
            return False
        coll = self._collections[collection_name]
        try:
            coll.delete(ids=[record_id])
            return True
        except Exception as e:
            logger.error("chroma_delete_failed", collection=collection_name, id=record_id, error=str(e))
            return False

    def delete_topic(self, topic: str) -> int:
        """Delete records matching a topic across all collections."""
        total_deleted = 0
        topic_lower = topic.lower()

        for name in self.COLLECTIONS:
            coll = self._collections.get(name)
            if not coll or coll.count() == 0:
                continue
            all_items = coll.get()
            ids_to_del: list[str] = []
            for item_id, doc in zip(all_items["ids"], all_items["documents"]):
                if topic_lower in doc.lower():
                    ids_to_del.append(item_id)
            if ids_to_del:
                coll.delete(ids=ids_to_del)
                total_deleted += len(ids_to_del)

        return total_deleted

    def count(self, collection_name: str) -> int:
        """Return number of documents in collection."""
        coll = self._collections.get(collection_name)
        return coll.count() if coll else 0


# Singleton
_chroma_store: ChromaMemoryStore | None = None


def get_chroma_store(persist_dir: Path | str | None = None) -> ChromaMemoryStore:
    """Return singleton Chroma memory store."""
    global _chroma_store
    if _chroma_store is None or persist_dir is not None:
        _chroma_store = ChromaMemoryStore(persist_dir or "data/chroma")
    return _chroma_store
