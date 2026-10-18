"""Measures real benchmark numbers for the README against a running local
server (`uvicorn src.main.backend.api.app:app --port 8001`) with a real
Vertex AI connection (Gemini + embeddings). Every metric here comes from an
actual HTTP call to the live system — nothing is estimated or invented.

Usage: .venv/bin/python -m src.main.backend.scripts.run_benchmarks

Writes src/main/backend/data/evaluation/benchmark_results.json.
"""
from __future__ import annotations

import json
import random
import statistics
import time
from pathlib import Path

import requests

from src.main.backend.store import load_default_store

BASE = "http://127.0.0.1:8001/api/v1"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "benchmark_results.json"

INVESTIGATE_PER_CATEGORY = 2
RAG_PER_CATEGORY = 10
LATENCY_REPS = 10


def _stratified_sample(store, per_category: int, seed: int) -> list[str]:
    by_category: dict[str, list[str]] = {}
    for gt in store.ground_truth.values():
        by_category.setdefault(gt.scenario_category, []).append(gt.incident_id)
    rng = random.Random(seed)
    sample = []
    for category, ids in sorted(by_category.items()):
        sample.extend(rng.sample(ids, min(per_category, len(ids))))
    return sample


def _timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def _percentile(values: list[float], pct: float) -> float:
    s = sorted(values)
    k = (len(s) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def bench_latency() -> dict:
    sample_id = next(iter(load_default_store().incidents))
    results = {}
    for label, fn in [
        ("health", lambda: requests.get(f"{BASE.replace('/api/v1', '')}/health")),
        ("reconcile", lambda: requests.post(f"{BASE}/incidents/{sample_id}/reconcile")),
        ("investigate", lambda: requests.post(f"{BASE}/incidents/{sample_id}/investigate")),
        ("similar_cases", lambda: requests.get(f"{BASE}/incidents/{sample_id}/similar-cases")),
    ]:
        durations = []
        for _ in range(LATENCY_REPS):
            resp, elapsed = _timed(fn)
            resp.raise_for_status()
            durations.append(elapsed)
        results[label] = {
            "reps": LATENCY_REPS,
            "mean_s": round(statistics.mean(durations), 3),
            "median_s": round(statistics.median(durations), 3),
            "p95_s": round(_percentile(durations, 0.95), 3),
            "min_s": round(min(durations), 3),
            "max_s": round(max(durations), 3),
        }
    return results


def bench_rag_relevance(store) -> dict:
    sample = _stratified_sample(store, RAG_PER_CATEGORY, seed=42)
    hit_at_1 = 0
    hit_at_k = 0
    total = 0
    methods_seen = set()
    per_call_latency = []
    for incident_id in sample:
        query_category = store.ground_truth[incident_id].scenario_category
        resp, elapsed = _timed(lambda: requests.get(f"{BASE}/incidents/{incident_id}/similar-cases?limit=5"))
        if resp.status_code != 200:
            continue
        hits = resp.json()
        if not hits:
            continue
        total += 1
        per_call_latency.append(elapsed)
        methods_seen.update(h["method"] for h in hits)
        result_categories = [
            store.ground_truth[h["incident_id"]].scenario_category
            for h in hits if h["incident_id"] in store.ground_truth
        ]
        if result_categories and result_categories[0] == query_category:
            hit_at_1 += 1
        if query_category in result_categories:
            hit_at_k += 1
    return {
        "sample_size": total,
        "per_category": RAG_PER_CATEGORY,
        "methods_observed": sorted(methods_seen),
        "category_match_at_1": round(hit_at_1 / total, 3) if total else None,
        "category_match_at_k": round(hit_at_k / total, 3) if total else None,
        "mean_latency_s": round(statistics.mean(per_call_latency), 3) if per_call_latency else None,
        "note": (
            "category_match measures whether the retrieved incident(s) share the query's "
            "ground-truth scenario_category label — a proxy for topical relevance, not a "
            "human relevance judgment."
        ),
    }


def bench_investigation_safety(store) -> dict:
    sample = _stratified_sample(store, INVESTIGATE_PER_CATEGORY, seed=7)
    total = 0
    live_count = 0
    citation_fabrication_events = 0
    total_citations_removed = 0
    policy_overrides = 0
    latencies = []
    model_identifiers = set()
    for incident_id in sample:
        requests.post(f"{BASE}/incidents/{incident_id}/reconcile")
        resp, elapsed = _timed(lambda: requests.post(f"{BASE}/incidents/{incident_id}/investigate"))
        if resp.status_code != 200:
            continue
        report = resp.json()
        total += 1
        latencies.append(elapsed)
        model_identifiers.add(report["model_identifier"])
        if report["source_mode"] == "LIVE":
            live_count += 1
        removed = len(report.get("unsupported_claims_removed", []))
        total_citations_removed += removed
        if removed > 0:
            citation_fabrication_events += 1
        if report.get("policy_override_applied"):
            policy_overrides += 1
    return {
        "sample_size": total,
        "per_category": INVESTIGATE_PER_CATEGORY,
        "live_vertex_calls": live_count,
        "model_identifiers_seen": sorted(model_identifiers),
        "investigations_with_fabricated_citation_stripped": citation_fabrication_events,
        "total_citations_stripped": total_citations_removed,
        "citation_fabrication_rate": round(citation_fabrication_events / total, 3) if total else None,
        "policy_override_rate": round(policy_overrides / total, 3) if total else None,
        "mean_latency_s": round(statistics.mean(latencies), 3) if latencies else None,
        "note": (
            "citation_fabrication_rate = share of investigations where at least one AI-cited "
            "evidence ID did not exist and was stripped before display. policy_override_rate = "
            "share where the AI's recommended action was outside the reconciliation engine's own "
            "permitted actions and was overridden. These measure the system's safety-net behavior, "
            "not narrative correctness of the AI's summary (which is not independently graded here)."
        ),
    }


def main() -> None:
    requests.get(f"{BASE.replace('/api/v1', '')}/health").raise_for_status()
    store = load_default_store()

    print("Running latency benchmark...")
    latency = bench_latency()
    print("Running RAG retrieval benchmark (live Vertex embeddings)...")
    rag = bench_rag_relevance(store)
    print("Running AI investigation safety benchmark (live Vertex Gemini)...")
    investigation = bench_investigation_safety(store)

    results = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency": latency,
        "rag_retrieval": rag,
        "investigation_safety": investigation,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
