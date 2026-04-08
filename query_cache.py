"""
Semantic Query Cache
====================
In-memory cache that matches queries by embedding cosine similarity.
- L1: exact string match (instant)
- L2: semantic similarity via cosine on embeddings (< 0.1s)

Pre-computed demo answers are loaded at startup as seed cache.
"""

import json
import os
import time
import numpy as np
from typing import Optional

SIMILARITY_THRESHOLD = 0.95
MAX_CACHE_SIZE = 500


class SemanticCache:
    def __init__(self, embed_fn):
        self._embed_fn = embed_fn
        self._entries: list[dict] = []
        self._exact_map: dict[str, str] = {}

    @staticmethod
    def _normalize(question: str) -> str:
        return question.strip().lower()

    def lookup(self, question: str) -> Optional[str]:
        """Check cache for a matching answer. Returns answer or None."""
        normalized = self._normalize(question)

        # L1: exact match
        if normalized in self._exact_map:
            return self._exact_map[normalized]

        # L2: semantic similarity
        if not self._entries:
            return None

        query_emb = np.array(self._embed_fn(question))
        embeddings = np.array([e["embedding"] for e in self._entries])

        # Cosine similarity (OpenAI embeddings are already normalized)
        similarities = embeddings @ query_emb
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= SIMILARITY_THRESHOLD:
            return self._entries[best_idx]["answer"]

        return None

    def store(self, question: str, answer: str, embedding: Optional[list] = None):
        """Store a question-answer pair in the cache."""
        normalized = self._normalize(question)
        self._exact_map[normalized] = answer

        if embedding is None:
            embedding = self._embed_fn(question)

        self._entries.append({
            "question": question,
            "embedding": np.array(embedding),
            "answer": answer,
            "created_at": time.time(),
        })

        if len(self._entries) > MAX_CACHE_SIZE:
            removed = self._entries.pop(0)
            removed_norm = self._normalize(removed["question"])
            self._exact_map.pop(removed_norm, None)

    def load_seed(self, seed_path: str) -> int:
        """Load pre-computed demo answers from JSON file."""
        if not os.path.exists(seed_path) or os.path.getsize(seed_path) == 0:
            return 0

        with open(seed_path, "r", encoding="utf-8") as f:
            seeds = json.load(f)

        count = 0
        for entry in seeds:
            question = entry["question"]
            answer = entry["answer"]
            embedding = entry.get("embedding")

            if embedding is None:
                embedding = self._embed_fn(question)

            self._exact_map[self._normalize(question)] = answer
            self._entries.append({
                "question": question,
                "embedding": np.array(embedding),
                "answer": answer,
                "created_at": time.time(),
            })
            count += 1

        return count

    @property
    def size(self) -> int:
        return len(self._entries)
