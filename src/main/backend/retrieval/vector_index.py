"""Vector index backed by Qdrant, running embedded/local (no server, no
Docker) — persists to a directory on disk via an embedded instance. Same
build()/load()/search() contract as before so callers (api/app.py,
build_rag_index.py) don't change; this is the swap-in point mentioned in
spec section 2's "modular interface allowing a future managed vector
database" — moving to a hosted Qdrant Cloud instance later only means
changing how the client connects (url= + api_key= instead of path=), not
touching this interface.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

DEFAULT_INDEX_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "rag_qdrant_db"
DEFAULT_META_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "rag_index_meta.json"
COLLECTION_NAME = "upitrace_rag"


@dataclass
class VectorIndex:
    model: str = ""
    provider_type: str = ""  # "vertex" | "ai_studio" — query embeddings must use the SAME
    # provider the index was built with, or distances are meaningless across
    # different vector spaces.
    _client: QdrantClient | None = field(default=None, repr=False)

    def search(self, query_vector: list[float], top_k: int = 5, kind: str | None = None) -> list[dict]:
        if self._client is None:
            return []
        query_filter = (
            Filter(must=[FieldCondition(key="kind", match=MatchValue(value=kind))]) if kind else None
        )
        hits = self._client.query_points(
            collection_name=COLLECTION_NAME, query=query_vector, limit=top_k,
            query_filter=query_filter, with_payload=True,
        ).points
        return [
            {"id": h.payload["ref_id"], "text": h.payload["text"], "kind": h.payload["kind"], "score": float(h.score)}
            for h in hits
        ]

    def save(self, index_path: Path = DEFAULT_INDEX_PATH, meta_path: Path = DEFAULT_META_PATH) -> None:
        # Qdrant's embedded/local mode writes through to disk as points are
        # upserted — nothing extra to flush. This just persists the small
        # sidecar (model/provider_type), which Qdrant itself doesn't track.
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({"model": self.model, "provider_type": self.provider_type}))

    @classmethod
    def load(cls, index_path: Path = DEFAULT_INDEX_PATH, meta_path: Path = DEFAULT_META_PATH) -> "VectorIndex | None":
        if not index_path.exists() or not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text())
        client = QdrantClient(path=str(index_path))
        if not client.collection_exists(COLLECTION_NAME):
            return None
        return cls(model=meta["model"], provider_type=meta.get("provider_type", "vertex"), _client=client)

    @classmethod
    def build(
        cls, ids: list[str], texts: list[str], kinds: list[str], vectors: list[list[float]],
        model: str, provider_type: str = "vertex", index_path: Path = DEFAULT_INDEX_PATH,
    ) -> "VectorIndex":
        client = QdrantClient(path=str(index_path))
        dim = len(vectors[0])
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME, vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        points = [
            PointStruct(id=i, vector=vectors[i], payload={"ref_id": ids[i], "text": texts[i], "kind": kinds[i]})
            for i in range(len(ids))
        ]
        # Upload in chunks — a single upsert of 10k+ points with full vectors
        # is a large request; Qdrant's own client handles batching for us.
        client.upload_points(collection_name=COLLECTION_NAME, points=points, batch_size=256)
        return cls(model=model, provider_type=provider_type, _client=client)
