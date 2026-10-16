"""Deterministic fake AI provider for automated tests and for honest demo
fallback when Vertex AI isn't configured (spec section 8: "Create a fake AI
provider for automated tests. If Vertex AI is unavailable, the UI must
clearly show that the deterministic fallback was used.").

This is NOT an LLM. It synthesizes the InvestigationReport's narrative fields
directly from the already-computed ReconciliationResult, citing only
evidence/runbook IDs that are genuinely present in the context. Every caller
sees `source_mode=SIMULATED` and `ai_used=False` so nothing is mistaken for a
real Gemini response.
"""
from __future__ import annotations

from typing import Any

from src.main.backend.investigation.schemas import InvestigationContext

CLASSIFICATION_SUMMARY = {
    "CONFIRMED": "Payment and merchant order both confirmed; no open questions.",
    "PENDING": "Payment is still pending at the provider; no conclusion is possible yet.",
    "STATUS_MISMATCH": "Two or more sources disagree about the outcome of this payment.",
    "MERCHANT_CONFIRMATION_MISSING": "Payment succeeded at the gateway, but merchant-side confirmation is absent or unprocessed.",
    "INSUFFICIENT_EVIDENCE": "The available records do not contain enough information to reach a conclusion.",
    "POSSIBLE_DUPLICATE": "More than one record could represent the same underlying payment; needs de-duplication before acting.",
    "REVERSAL_UNVERIFIED": "A refund or reversal is expected or requested, but there is no confirmation it has actually happened.",
    "UNRESOLVED": "No deterministic rule matched this combination of evidence; needs manual review.",
}


class FakeAIProvider:
    model_identifier = "fake-deterministic-v1"
    source_mode = "SIMULATED"

    def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
        recon = context.reconciliation
        allowed = context.allowed_citation_ids()

        supporting = [eid for eid in recon.evidence_ids if eid in allowed]
        hypotheses = list(recon.conflicts) or [
            "Single, uncontested explanation consistent with " + recon.classification.value
        ]

        summary = CLASSIFICATION_SUMMARY.get(
            recon.classification.value, f"Classification: {recon.classification.value}."
        )

        return {
            "summary": summary,
            "confirmed_facts": list(recon.confirmed_facts),
            "competing_hypotheses": hypotheses,
            "supporting_evidence": supporting,
            "contradicting_evidence": [] if not recon.conflicts else supporting,
            "missing_evidence": list(recon.missing_evidence),
            "recommended_checks": list(recon.permitted_checks),
            "recommended_next_action": (
                recon.permitted_checks[0] if recon.permitted_checks else "No action required."
            ),
            "reasoning": (
                f"Deterministic reconciliation classified this incident as "
                f"{recon.classification.value} via rules {recon.rules_applied}. "
                f"{len(supporting)} evidence record(s) support this; "
                f"{len(recon.missing_evidence)} item(s) remain missing."
            ),
            "uncertainty_explanation": (
                "; ".join(recon.unresolved_questions) if recon.unresolved_questions
                else "No material uncertainty beyond what is listed above."
            ),
            "citation_ids": supporting,
            "unresolved_status": recon.classification.value in (
                "PENDING", "INSUFFICIENT_EVIDENCE", "STATUS_MISMATCH",
                "POSSIBLE_DUPLICATE", "REVERSAL_UNVERIFIED", "UNRESOLVED",
            ),
        }
