"""One-time (well — re-run whenever data changes) batch job: embeds every
incident (title + complaint) and every runbook (title + content), and saves
the resulting vector index to disk.

Vertex AI is the explicit, selected production embedding provider (ADC,
VERTEX_EMBEDDING_MODEL) — no silent fallback to the AI Studio API if Vertex
fails. Pass --use-ai-studio explicitly for local dev/testing with the free
GEMINI_API_KEY path instead.

This is deliberately NOT run automatically on server startup — it costs real
API quota and takes real time, so it is an explicit, separate step. The API
server loads whatever index already exists on disk (store.py /
retrieval/vector_index.py), and the `/similar-cases` route falls back to
lexical-only search if no index file is present yet — same honest-fallback
pattern as the chat AI providers.

Usage:
    python -m src.main.backend.scripts.build_rag_index [--limit N]
    python -m src.main.backend.scripts.build_rag_index --use-ai-studio   # dev only
"""
from __future__ import annotations

import argparse
import sys
import time

from src.main.backend.ai.exceptions import AIProviderUnavailable
from src.main.backend.retrieval.embeddings import MAX_BATCH_SIZE, GeminiEmbeddingProvider, VertexEmbeddingProvider
from src.main.backend.retrieval.vector_index import DEFAULT_INDEX_PATH, VectorIndex
from src.main.backend.store import load_default_store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Embed only the first N incidents (for a quick test run).")
    parser.add_argument("--batch-delay", type=float, default=0.5, help="Seconds to sleep between batches (be polite to rate limits).")
    parser.add_argument("--use-ai-studio", action="store_true", help="Dev/testing only: use the free AI Studio embedding API instead of Vertex AI.")
    args = parser.parse_args()

    try:
        if args.use_ai_studio:
            provider = GeminiEmbeddingProvider()
        else:
            provider = VertexEmbeddingProvider()
    except AIProviderUnavailable as exc:
        print(f"Cannot build RAG index: {exc}", file=sys.stderr)
        if args.use_ai_studio:
            print("Set GEMINI_API_KEY (https://aistudio.google.com/apikey) and re-run.", file=sys.stderr)
        else:
            print(
                "Set GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_EMBEDDING_MODEL, "
                "and run `gcloud auth application-default login`. Or pass --use-ai-studio for dev.",
                file=sys.stderr,
            )
        sys.exit(1)

    store = load_default_store()
    incidents = list(store.incidents.values())
    if args.limit:
        incidents = incidents[: args.limit]
    runbooks = list(store.runbooks.values())

    ids = [i.incident_id for i in incidents] + [r.runbook_id for r in runbooks]
    texts = [f"{i.title}. {i.complaint}" for i in incidents] + [f"{r.title}. {r.content}" for r in runbooks]
    kinds = ["incident"] * len(incidents) + ["runbook"] * len(runbooks)

    print(f"Embedding {len(texts)} documents ({len(incidents)} incidents + {len(runbooks)} runbooks) "
          f"via {provider.model}, batches of {MAX_BATCH_SIZE}...")

    vectors: list[list[float]] = []
    num_batches = (len(texts) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
    start_time = time.time()
    for b in range(num_batches):
        chunk = texts[b * MAX_BATCH_SIZE:(b + 1) * MAX_BATCH_SIZE]
        chunk_vectors = provider.embed_batch(chunk)
        vectors.extend(chunk_vectors)
        elapsed = time.time() - start_time
        print(f"  batch {b + 1}/{num_batches} done ({len(vectors)}/{len(texts)} embedded, {elapsed:.1f}s elapsed)")
        if b < num_batches - 1:
            time.sleep(args.batch_delay)

    index = VectorIndex.build(
        ids=ids, texts=texts, kinds=kinds, vectors=vectors, model=provider.model,
        provider_type="ai_studio" if args.use_ai_studio else "vertex",
    )
    index.save()
    print(f"Saved Qdrant collection with {len(ids)} vectors to {DEFAULT_INDEX_PATH}")


if __name__ == "__main__":
    main()
