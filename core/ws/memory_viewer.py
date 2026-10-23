"""T.A.R.O. - Memory Viewer backend (TASK-087).

ARCHITECTURE reference: section 12 (Memory), section 24 (HUD).
TASKS: TASK-087.

Provides unified view and management of the three-tier memory system:
  - Tier 1 (SQLite): Conversation history, tool logs, summaries.
  - Tier 2 (ChromaDB): Semantic vector memory.
  - Tier 3 (JSON): Workflow definitions, user preferences.

Acceptance (TASK-087): Delete removes all three stores.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


class MemoryViewer:
    """Unified read/search/delete interface across all three memory tiers."""

    def __init__(
        self,
        sqlite_path: Path | str | None = None,
        chroma_collection: Any = None,
        json_dir: Path | str | None = None,
    ) -> None:
        self._sqlite_path = Path(sqlite_path) if sqlite_path else Path("data/memory.db")
        self._chroma = chroma_collection
        self._json_dir = Path(json_dir) if json_dir else Path("data/json_memory")

    # ----- Tier 1: SQLite -----

    def list_sqlite_entries(
        self, table: str = "conversations", limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List entries from SQLite memory store."""
        entries = []
        if not self._sqlite_path.exists():
            return entries

        try:
            conn = sqlite3.connect(str(self._sqlite_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT rowid, * FROM {table} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            for row in cursor:
                entries.append(dict(row))
            conn.close()
        except Exception as e:
            logger.warning("sqlite_list_error", error=str(e))
        return entries

    def delete_sqlite_entry(self, table: str, rowid: int) -> bool:
        """Delete a specific entry from SQLite."""
        if not self._sqlite_path.exists():
            return False
        try:
            conn = sqlite3.connect(str(self._sqlite_path))
            conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
            conn.commit()
            conn.close()
            logger.info("sqlite_entry_deleted", table=table, rowid=rowid)
            return True
        except Exception as e:
            logger.warning("sqlite_delete_error", error=str(e))
            return False

    # ----- Tier 2: ChromaDB -----

    def list_chroma_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """List entries from ChromaDB semantic memory."""
        if self._chroma is None:
            return []
        try:
            results = self._chroma.peek(limit=limit)
            entries = []
            if results and "ids" in results:
                for i, doc_id in enumerate(results["ids"]):
                    entry = {"id": doc_id, "store": "chroma"}
                    if "documents" in results and i < len(results["documents"]):
                        entry["document"] = results["documents"][i]
                    if "metadatas" in results and i < len(results["metadatas"]):
                        entry["metadata"] = results["metadatas"][i]
                    entries.append(entry)
            return entries
        except Exception as e:
            logger.warning("chroma_list_error", error=str(e))
            return []

    def search_chroma(self, query: str, n_results: int = 10) -> list[dict[str, Any]]:
        """Semantic search across ChromaDB memory."""
        if self._chroma is None:
            return []
        try:
            results = self._chroma.query(query_texts=[query], n_results=n_results)
            entries = []
            if results and "ids" in results:
                for i, doc_id in enumerate(results["ids"][0]):
                    entry = {"id": doc_id, "store": "chroma"}
                    if "documents" in results and i < len(results["documents"][0]):
                        entry["document"] = results["documents"][0][i]
                    if "distances" in results and i < len(results["distances"][0]):
                        entry["distance"] = results["distances"][0][i]
                    entries.append(entry)
            return entries
        except Exception as e:
            logger.warning("chroma_search_error", error=str(e))
            return []

    def delete_chroma_entry(self, doc_id: str) -> bool:
        """Delete a specific entry from ChromaDB."""
        if self._chroma is None:
            return False
        try:
            self._chroma.delete(ids=[doc_id])
            logger.info("chroma_entry_deleted", id=doc_id)
            return True
        except Exception as e:
            logger.warning("chroma_delete_error", error=str(e))
            return False

    # ----- Tier 3: JSON -----

    def list_json_entries(self) -> list[dict[str, Any]]:
        """List all JSON memory entries."""
        entries = []
        if not self._json_dir.exists():
            return entries
        for jfile in sorted(self._json_dir.glob("*.json")):
            try:
                with open(jfile, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entries.append({
                    "id": jfile.stem,
                    "store": "json",
                    "file": jfile.name,
                    "data": data,
                })
            except Exception as e:
                logger.warning("json_read_error", file=jfile.name, error=str(e))
        return entries

    def delete_json_entry(self, entry_id: str) -> bool:
        """Delete a JSON memory file."""
        target = self._json_dir / f"{entry_id}.json"
        if target.exists():
            target.unlink()
            logger.info("json_entry_deleted", id=entry_id)
            return True
        return False

    # ----- Unified Operations -----

    def get_all_entries(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get entries from all three stores combined."""
        entries = []

        # SQLite
        sqlite_entries = self.list_sqlite_entries(limit=limit)
        for e in sqlite_entries:
            e["store"] = "sqlite"
        entries.extend(sqlite_entries)

        # ChromaDB
        chroma_entries = self.list_chroma_entries(limit=limit)
        entries.extend(chroma_entries)

        # JSON
        json_entries = self.list_json_entries()
        entries.extend(json_entries[:limit])

        return entries

    def delete_entry_all_stores(self, entry_id: str) -> list[str]:
        """Delete an entry from ALL stores. Returns list of stores affected."""
        deleted_from: list[str] = []

        # Try SQLite (uses rowid)
        try:
            rowid = int(entry_id)
            if self.delete_sqlite_entry("conversations", rowid):
                deleted_from.append("sqlite")
        except (ValueError, TypeError):
            pass

        # Try ChromaDB
        if self.delete_chroma_entry(entry_id):
            deleted_from.append("chroma")

        # Try JSON
        if self.delete_json_entry(entry_id):
            deleted_from.append("json")

        logger.info("memory_entry_deleted_all", id=entry_id, stores=deleted_from)
        return deleted_from

    def get_stats(self) -> dict[str, Any]:
        """Get memory usage statistics."""
        stats: dict[str, Any] = {}

        # SQLite size
        if self._sqlite_path.exists():
            stats["sqlite_size_kb"] = round(self._sqlite_path.stat().st_size / 1024, 1)
        else:
            stats["sqlite_size_kb"] = 0

        # JSON count
        if self._json_dir.exists():
            stats["json_count"] = len(list(self._json_dir.glob("*.json")))
        else:
            stats["json_count"] = 0

        # ChromaDB count
        if self._chroma:
            try:
                stats["chroma_count"] = self._chroma.count()
            except Exception:
                stats["chroma_count"] = 0
        else:
            stats["chroma_count"] = 0

        return stats
