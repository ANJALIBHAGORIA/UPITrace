"""Tests for the RAG pipeline: embeddings (fails closed without a key) and
the Qdrant-backed vector index's search behavior (embedded/local mode, no
network or server needed for this part)."""
import pytest

from src.main.backend.ai.exceptions import AIProviderUnavailable
from src.main.backend.retrieval.embeddings import GeminiEmbeddingProvider, VertexEmbeddingProvider
from src.main.backend.retrieval.vector_index import VectorIndex


def test_embedding_provider_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AIProviderUnavailable, match="GEMINI_API_KEY"):
        GeminiEmbeddingProvider()


def test_vertex_embedding_provider_unavailable_without_model_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_EMBEDDING_MODEL", raising=False)
    with pytest.raises(AIProviderUnavailable, match="VERTEX_EMBEDDING_MODEL"):
        VertexEmbeddingProvider()


def test_vector_index_returns_nearest_by_cosine_similarity(tmp_path):
    index = VectorIndex.build(
        ids=["a", "b", "c"],
        texts=["payer debited, no merchant confirmation", "order confirmed and settled", "unrelated"],
        kinds=["incident", "incident", "incident"],
        vectors=[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
        model="test-model", index_path=tmp_path / "db1",
    )
    results = index.search([1.0, 0.0], top_k=2)
    assert [r["id"] for r in results] == ["a", "b"]
    assert results[0]["score"] > results[1]["score"]


def test_vector_index_filters_by_kind(tmp_path):
    index = VectorIndex.build(
        ids=["i1", "r1"], texts=["incident text", "runbook text"],
        kinds=["incident", "runbook"], vectors=[[1.0, 0.0], [1.0, 0.0]], model="test-model",
        index_path=tmp_path / "db2",
    )
    results = index.search([1.0, 0.0], top_k=5, kind="runbook")
    assert len(results) == 1
    assert results[0]["id"] == "r1"


def test_vector_index_save_and_load_roundtrip(tmp_path):
    index_path = tmp_path / "db3"
    meta_path = tmp_path / "idx_meta.json"
    original = VectorIndex.build(
        ids=["x", "y"], texts=["hello", "world"], kinds=["incident", "incident"],
        vectors=[[0.6, 0.8], [0.1, 0.9]], model="test-model", index_path=index_path,
    )
    original.save(index_path=index_path, meta_path=meta_path)
    del original  # release the embedded Qdrant instance's file lock before reopening

    loaded = VectorIndex.load(index_path=index_path, meta_path=meta_path)
    assert loaded is not None
    assert loaded.model == "test-model"
    results = loaded.search([0.6, 0.8], top_k=1)
    assert results[0]["id"] == "x"


def test_vector_index_load_returns_none_when_missing(tmp_path):
    assert VectorIndex.load(index_path=tmp_path / "nope_db", meta_path=tmp_path / "nope.json") is None
