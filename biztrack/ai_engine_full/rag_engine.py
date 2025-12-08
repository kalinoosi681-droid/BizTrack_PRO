# ========================================
# biztrack/ai_engine/rag_engine.py - RAG System
# ========================================
import logging
import json
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Lightweight RAG Engine using a SQLite-backed document store.

    - Stores documents and their embeddings in the application database.
    - Uses an LLM handler (e.g., Ollama) to generate embeddings when available.
    - Provides a simple cosine-similarity search for top-k documents.

    This implementation intentionally avoids heavy dependencies so it can
    run in constrained environments. It's designed to be a practical
    step-up from a placeholder while remaining lightweight.
    """

    def __init__(self, db_connection):
        self.db = db_connection
        self._ensure_table()

    def _ensure_table(self):
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    embedding TEXT
                );
                """
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to ensure RAG table exists: {e}")

    def add_document(self, content: str, metadata: Optional[Dict] = None, llm_handler=None) -> bool:
        """Add a document to the local vector store. Optionally embed using llm_handler."""
        try:
            embedding = None
            if llm_handler:
                try:
                    emb = llm_handler.embed_text(content)
                    embedding = json.dumps(emb)
                except Exception as e:
                    logger.warning(f"Failed to embed document: {e}")

            self.db.execute(
                "INSERT INTO rag_documents (content, metadata, embedding) VALUES (?, ?, ?)",
                (content, json.dumps(metadata or {}), embedding),
            )
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add RAG document: {e}")
            return False

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        try:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)
        except Exception:
            return 0.0

    def search(self, query: str, top_k: int = 5, llm_handler=None) -> List[Dict]:
        """
        Search for relevant documents. If `llm_handler` is provided, use it to
        embed the query and compute cosine similarity against stored embeddings.
        Falls back to returning lightweight, internal context if embeddings are
        not available.
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT id, content, metadata, embedding FROM rag_documents")
            rows = cursor.fetchall()

            # If we have no stored docs, return a helpful default.
            if not rows:
                logger.info("RAG: no documents indexed yet.")
                return [{"content": f"No indexed documents available for query '{query}'.", "score": 0.0}]

            # If we have an LLM handler, attempt to embed the query.
            query_emb = None
            if llm_handler:
                try:
                    query_emb = llm_handler.embed_text(query)
                except Exception as e:
                    logger.warning(f"Failed to embed query: {e}")

            candidates = []
            for r in rows:
                doc_id, content, metadata_json, emb_json = r
                score = 0.0
                if query_emb and emb_json:
                    try:
                        doc_emb = json.loads(emb_json)
                        score = self._cosine_similarity(query_emb, doc_emb)
                    except Exception:
                        score = 0.0
                candidates.append({"id": doc_id, "content": content, "metadata": json.loads(metadata_json or '{}'), "score": score})

            # Sort by score descending
            candidates.sort(key=lambda x: x['score'], reverse=True)

            # Return top_k; if scores are all zero, provide a fallback message.
            if all(c['score'] == 0 for c in candidates[:top_k]):
                return [{"content": f"No semantically-relevant docs found for '{query}'.", "score": 0.0}]

            return candidates[:top_k]

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return [{"content": f"RAG search error: {e}", "score": 0.0}]