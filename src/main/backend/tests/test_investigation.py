"""Phase 3 acceptance tests: fake AI provider, citation verification, hybrid
retrieval, and the orchestrator's policy-check/fallback behavior."""
import os
from typing import Any

import pytest

from src.main.backend.ai.exceptions import AIProviderUnavailable
from src.main.backend.ai.fake_provider import FakeAIProvider
from src.main.backend.ai.vertex_provider import VertexGeminiProvider
from src.main.backend.investigation.citation_verification import verify_and_strip_citations
from src.main.backend.investigation.orchestrator import run_investigation
from src.main.backend.investigation.schemas import InvestigationContext
from src.main.backend.models import SourceMode
from src.main.backend.reconciliation import apply_reconciliation
from src.main.backend.retrieval.hybrid import retrieve_runbooks_hybrid, retrieve_similar_incidents
from src.main.backend.store import load_default_store


def _store():
    return load_default_store()


# -- citation verification ---------------------------------------------------

def test_verify_and_strip_citations_keeps_only_allowed_ids():
    valid, removed = verify_and_strip_citations(
        ["EVD-0001", "EVD-9999", "EVD-0001"], allowed_ids={"EVD-0001", "EVD-0002"},
    )
    assert valid == ["EVD-0001"]  # de-duplicated
    assert removed == ["EVD-9999"]


def test_verify_and_strip_citations_empty_input():
    valid, removed = verify_and_strip_citations([], allowed_ids={"EVD-0001"})
    assert valid == [] and removed == []


# -- fake provider ------------------------------------------------------------

def test_fake_provider_only_cites_evidence_actually_in_context():
    store = _store()
    incident_id = next(
        i.incident_id for i in store.incidents.values() if "Conflicting status" in i.title
    )
    reconciliation = apply_reconciliation(store, incident_id)
    evidence = store.evidence_for_incident(incident_id)
    context = InvestigationContext(incident=store.incidents[incident_id], reconciliation=reconciliation,
                                    evidence=evidence)
    raw = FakeAIProvider().generate_investigation(context)
    allowed = context.allowed_citation_ids()
    assert set(raw["citation_ids"]).issubset(allowed)


def test_fake_provider_reflects_abstention_for_insufficient_evidence():
    store = _store()
    incident_id = next(
        i.incident_id for i in store.incidents.values() if "Unclear outcome" in i.title
    )
    reconciliation = apply_reconciliation(store, incident_id)
    context = InvestigationContext(incident=store.incidents[incident_id], reconciliation=reconciliation,
                                    evidence=store.evidence_for_incident(incident_id))
    raw = FakeAIProvider().generate_investigation(context)
    assert raw["unresolved_status"] is True
    assert reconciliation.classification.value == "INSUFFICIENT_EVIDENCE"


# -- hybrid retrieval ----------------------------------------------------------

def test_retrieve_similar_incidents_excludes_self_and_scores_are_bounded():
    store = _store()
    incident = next(iter(store.incidents.values()))
    results = retrieve_similar_incidents(store, incident, limit=5)
    assert all(r.incident.incident_id != incident.incident_id for r in results)
    assert all(0.0 < r.combined_score <= 1.0 for r in results)


def test_retrieve_runbooks_hybrid_prefers_tag_match():
    store = _store()
    results = retrieve_runbooks_hybrid(store, "DUPLICATE_NOTIFICATION")
    assert results
    assert results[0].matched_tag is True


# -- orchestrator: fallback & policy enforcement --------------------------------

def test_orchestrator_falls_back_honestly_when_no_provider_given_and_vertex_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    store = _store()
    incident_id = next(iter(store.incidents))
    report = run_investigation(store, incident_id, provider=None)
    assert report.ai_used is False
    assert report.source_mode == SourceMode.UNAVAILABLE
    assert report.model_identifier == "none (deterministic fallback)"


def test_orchestrator_uses_explicit_fake_provider_and_reports_simulated():
    store = _store()
    incident_id = next(iter(store.incidents))
    report = run_investigation(store, incident_id, provider=FakeAIProvider())
    assert report.ai_used is True
    assert report.source_mode == SourceMode.SIMULATED
    assert report.model_identifier == "fake-deterministic-v1"


def test_orchestrator_strips_invented_citations_from_a_misbehaving_provider():
    class LyingProvider:
        model_identifier = "lying-v1"
        source_mode = "SIMULATED"

        def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
            return {
                "summary": "s", "confirmed_facts": [], "competing_hypotheses": [],
                "supporting_evidence": ["EVD-INVENTED-123"],
                "contradicting_evidence": [], "missing_evidence": [],
                "recommended_checks": [],
                "recommended_next_action": context.reconciliation.permitted_checks[0]
                if context.reconciliation.permitted_checks else "No action required.",
                "reasoning": "r", "uncertainty_explanation": "u",
                "citation_ids": ["EVD-INVENTED-123", "EVD-ALSO-FAKE"],
                "unresolved_status": False,
            }

    store = _store()
    incident_id = next(iter(store.incidents))
    report = run_investigation(store, incident_id, provider=LyingProvider())
    assert report.citation_ids == []  # both invented IDs stripped
    assert set(report.unsupported_claims_removed) == {"EVD-INVENTED-123", "EVD-ALSO-FAKE"}


def test_orchestrator_overrides_an_unsafe_recommended_action():
    """A provider recommending something outside the reconciliation engine's
    own permitted_checks must be overridden, not trusted."""
    class RecklessProvider:
        model_identifier = "reckless-v1"
        source_mode = "SIMULATED"

        def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
            return {
                "summary": "s", "confirmed_facts": [], "competing_hypotheses": [],
                "supporting_evidence": [], "contradicting_evidence": [], "missing_evidence": [],
                "recommended_checks": [],
                "recommended_next_action": "tell_customer_refund_is_complete",  # not permitted
                "reasoning": "r", "uncertainty_explanation": "u",
                "citation_ids": [], "unresolved_status": True,
            }

    store = _store()
    # REVERSAL_MISSING_OR_PENDING incidents have a non-empty permitted_checks list
    # ("query_reversal_status") that explicitly forbids declaring the refund done.
    incident_id = next(
        i.incident_id for i in store.incidents.values() if "No reversal seen" in i.title
    )
    report = run_investigation(store, incident_id, provider=RecklessProvider())
    assert report.policy_override_applied is True
    assert report.recommended_next_action == "query_reversal_status"
    assert report.recommended_next_action != "tell_customer_refund_is_complete"


def test_orchestrator_schema_validation_rejects_incomplete_provider_output():
    class BrokenProvider:
        model_identifier = "broken-v1"
        source_mode = "SIMULATED"

        def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
            return {"summary": "s"}  # missing required fields

    store = _store()
    incident_id = next(iter(store.incidents))
    with pytest.raises(ValueError, match="missing required fields"):
        run_investigation(store, incident_id, provider=BrokenProvider())


# -- real Vertex provider: confirm it fails closed, not open --------------------

def test_vertex_provider_unavailable_without_project_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(AIProviderUnavailable, match="GOOGLE_CLOUD_PROJECT"):
        VertexGeminiProvider()


def test_vertex_provider_unavailable_without_model_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    monkeypatch.delenv("VERTEX_AI_GEMINI_MODEL", raising=False)
    with pytest.raises(AIProviderUnavailable, match="VERTEX_AI_GEMINI_MODEL"):
        VertexGeminiProvider()
