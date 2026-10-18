"""Text embeddings for the RAG index.

`VertexEmbeddingProvider` (below) is the production path — ADC-based, no
API key, matching the chat-provider migration to Vertex AI.

`GeminiEmbeddingProvider` (free-tier Google AI Studio, GEMINI_API_KEY) is
kept for local dev/testing only — it is never auto-selected by
build_rag_index.py or the API when Vertex is configured; there is no silent
Vertex-fails-so-use-AI-Studio cascade, consistent with the chat provider.
"""
from __future__ import annotations

import os

import httpx

from src.main.backend.ai.exceptions import AIProviderUnavailable

_BATCH_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
)
_SINGLE_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
)
DEFAULT_MODEL = "text-embedding-004"
MAX_BATCH_SIZE = 100  # API limit for batchEmbedContents


class VertexEmbeddingProvider:
    """Vertex AI embeddings via google-genai in Vertex mode. Model ID is
    required explicitly (VERTEX_EMBEDDING_MODEL) — same "don't assume an
    AI-Studio model ID transfers" principle as the chat provider."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("VERTEX_EMBEDDING_MODEL", "")
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT", "upitrace")
        self._location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        if not self.model:
            raise AIProviderUnavailable("VERTEX_EMBEDDING_MODEL is not set.")
        try:
            from google import genai
        except ImportError as exc:
            raise AIProviderUnavailable(f"google-genai not installed: {exc}") from exc
        try:
            self._client = genai.Client(vertexai=True, project=self._project, location=self._location)
        except Exception as exc:
            raise AIProviderUnavailable(f"Vertex AI client initialization failed: {exc}") from exc

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.models.embed_content(model=self.model, contents=texts)
            return [e.values for e in response.embeddings]
        except Exception as exc:
            raise AIProviderUnavailable(f"Vertex AI embedding call failed: {exc}") from exc


class GeminiEmbeddingProvider:
    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_EMBEDDING_MODEL", DEFAULT_MODEL)
        if not self.api_key:
            raise AIProviderUnavailable("GEMINI_API_KEY is not set.")

    def embed_one(self, text: str) -> list[float]:
        url = _SINGLE_ENDPOINT.format(model=self.model)
        try:
            resp = httpx.post(
                url, params={"key": self.api_key}, timeout=30.0,
                json={"model": f"models/{self.model}", "content": {"parts": [{"text": text}]}},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]
        except Exception as exc:
            raise AIProviderUnavailable(f"Gemini embedding call failed: {exc}") from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds in chunks of MAX_BATCH_SIZE, preserving input order."""
        url = _BATCH_ENDPOINT.format(model=self.model)
        results: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            chunk = texts[start:start + MAX_BATCH_SIZE]
            requests = [
                {"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}}
                for t in chunk
            ]
            try:
                resp = httpx.post(
                    url, params={"key": self.api_key}, timeout=60.0,
                    json={"requests": requests},
                )
                resp.raise_for_status()
                embeddings = resp.json()["embeddings"]
            except Exception as exc:
                raise AIProviderUnavailable(
                    f"Gemini batch embedding call failed at offset {start}: {exc}"
                ) from exc
            results.extend(e["values"] for e in embeddings)
        return results
