"""Hybrid lexical + local "dense proxy" retrieval (spec section 2 and section
8, step 6).

Honesty note: `_dense_proxy_score` is a deterministic local term-frequency
cosine similarity, NOT a real embedding model. There is no Vertex AI
embeddings call here (no credentials on this machine — see
docs/architecture.md). It exists purely so the interface already looks like
"lexical score + vector score combined with metadata filtering", and the one
function to swap for real Vertex AI embeddings later is `_dense_proxy_score`
(or the whole scoring step, replaced by a managed vector index per the
spec's "modular interface allowing a future managed vector database").
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from src.main.backend.models import Incident, Runbook
from src.main.backend.store import InMemoryStore

LEXICAL_WEIGHT = 0.5
DENSE_PROXY_WEIGHT = 0.5


def _tokenize(text: str) -> list[str]:
    return [w.strip(".,!?#").lower() for w in text.split() if len(w) > 2]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _dense_proxy_score(text_a: str, text_b: str) -> float:
    """Cosine similarity over raw term-frequency vectors. A stand-in for a
    real embedding's cosine similarity — same shape of computation, much
    weaker semantics (no notion of synonymy, word order, etc.)."""
    vec_a = Counter(_tokenize(text_a))
    vec_b = Counter(_tokenize(text_b))
    if not vec_a or not vec_b:
        return 0.0
    shared = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class ScoredIncident:
    incident: Incident
    lexical_score: float
    dense_proxy_score: float
    combined_score: float
    shared_terms: list[str]


@dataclass
class ScoredRunbook:
    runbook: Runbook
    combined_score: float
    matched_tag: bool


def retrieve_similar_incidents(
    store: InMemoryStore,
    incident: Incident,
    *,
    limit: int = 3,
    classification_filter: str | None = None,
) -> list[ScoredIncident]:
    """Metadata filtering (by reconciliation_status, if given) followed by
    combined lexical + dense-proxy scoring over title+complaint text."""
    target_text = incident.title + " " + incident.complaint
    target_terms = set(_tokenize(target_text))

    candidates = [i for i in store.incidents.values() if i.incident_id != incident.incident_id]
    if classification_filter:
        candidates = [
            i for i in candidates
            if i.reconciliation_status is not None
            and i.reconciliation_status.value == classification_filter
        ] or candidates  # fall back to unfiltered if the filter empties the pool

    scored = []
    for other in candidates:
        other_text = other.title + " " + other.complaint
        other_terms = set(_tokenize(other_text))
        lex = _jaccard(target_terms, other_terms)
        dense = _dense_proxy_score(target_text, other_text)
        combined = LEXICAL_WEIGHT * lex + DENSE_PROXY_WEIGHT * dense
        if combined > 0:
            scored.append(ScoredIncident(
                incident=other, lexical_score=round(lex, 3), dense_proxy_score=round(dense, 3),
                combined_score=round(combined, 3), shared_terms=sorted(target_terms & other_terms),
            ))
    scored.sort(key=lambda s: s.combined_score, reverse=True)
    return scored[:limit]


def retrieve_runbooks_hybrid(
    store: InMemoryStore, classification: str, query: str = "", limit: int = 5
) -> list[ScoredRunbook]:
    scored = []
    for rb in store.runbooks.values():
        matched_tag = classification in rb.scenario_tags
        text_score = _dense_proxy_score(query or classification, rb.title + " " + rb.content)
        combined = (1.0 if matched_tag else 0.0) * 0.6 + text_score * 0.4
        if combined > 0:
            scored.append(ScoredRunbook(runbook=rb, combined_score=round(combined, 3), matched_tag=matched_tag))
    scored.sort(key=lambda s: s.combined_score, reverse=True)
    return scored[:limit]
