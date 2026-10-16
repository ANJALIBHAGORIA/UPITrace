"""Evaluation harness (spec section 10).

IMPORTANT: Vertex AI credentials are not configured on this machine (see
docs/architecture.md). This script evaluates the pipeline using
`FakeAIProvider` — a deterministic, non-LLM stand-in — for every incident.
The numbers below measure "does the orchestrator's plumbing behave
correctly" (citation verification, policy checks, reconciliation accuracy),
NOT "how good is Gemini at this task." Re-run with a real
`VertexGeminiProvider` once credentials are available before citing these as
real-world investigation quality numbers.

Usage:
    python -m src.main.backend.scripts.evaluate_investigation
"""
from __future__ import annotations

import time

from src.main.backend.ai.fake_provider import FakeAIProvider
from src.main.backend.investigation.orchestrator import run_investigation
from src.main.backend.store import load_default_store


def main() -> None:
    store = load_default_store()
    provider = FakeAIProvider()

    total = 0
    reconciliation_correct = 0
    safe_action_correct = 0
    correct_abstention = 0
    total_unresolvable = 0
    total_citations_offered = 0
    total_citations_unsupported = 0
    failures: list[str] = []
    latencies_ms: list[float] = []

    for incident_id, incident in store.incidents.items():
        gt = store.ground_truth.get(incident_id)
        if gt is None:
            continue
        total += 1

        start = time.perf_counter()
        try:
            report = run_investigation(store, incident_id, provider=provider)
        except Exception as exc:  # noqa: BLE001 - we want to count & report, not crash the run
            failures.append(f"{incident_id}: {exc}")
            continue
        latencies_ms.append((time.perf_counter() - start) * 1000)

        # reconciliation_status was written onto the incident by apply_reconciliation
        reconciled_status = store.incidents[incident_id].reconciliation_status
        if reconciled_status is not None and reconciled_status == gt.expected_reconciliation_status:
            reconciliation_correct += 1

        if not gt.is_resolvable:
            total_unresolvable += 1
            if report.unresolved_status:
                correct_abstention += 1

        # "Safe action" proxy: the recommended action must not have required a
        # policy override (i.e., the provider's own suggestion was already
        # within the reconciliation engine's permitted_checks).
        if not report.policy_override_applied:
            safe_action_correct += 1

        total_citations_offered += len(report.raw_provider_output.get("citation_ids", []))
        total_citations_unsupported += len(report.unsupported_claims_removed)

    print("=" * 70)
    print("UPITrace Phase 3 evaluation (FakeAIProvider — NOT real Gemini)")
    print("=" * 70)
    print(f"Incidents evaluated:                 {total}")
    print(f"Reconciliation accuracy:             {reconciliation_correct}/{total} "
          f"({reconciliation_correct / total:.0%})" if total else "n/a")
    print(f"Safe-action rate (no override needed): {safe_action_correct}/{total} "
          f"({safe_action_correct / total:.0%})" if total else "n/a")
    print(f"Correct abstention on unresolvable:  {correct_abstention}/{total_unresolvable} "
          f"({correct_abstention / total_unresolvable:.0%})" if total_unresolvable else "n/a (no unresolvable cases)")
    print(f"Citations offered:                   {total_citations_offered}")
    print(f"Citations rejected as unsupported:   {total_citations_unsupported}")
    print(f"Citation validity rate:              "
          f"{(total_citations_offered - total_citations_unsupported) / total_citations_offered:.0%}"
          if total_citations_offered else "n/a (no citations offered)")
    if latencies_ms:
        print(f"Latency (fake provider, no network): avg {sum(latencies_ms)/len(latencies_ms):.2f}ms, "
              f"max {max(latencies_ms):.2f}ms")
    print(f"Pipeline failures:                   {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    print()
    print("NOTE: citation validity is near-100% here because FakeAIProvider only ever")
    print("cites evidence it was actually given — this measures the verification")
    print("plumbing works, not what a real Gemini call would produce.")


if __name__ == "__main__":
    main()
