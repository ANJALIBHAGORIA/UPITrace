"""Investigation orchestrator — the 13-step pipeline from spec section 8.

    1.  Load the incident.
    2.  Run deterministic reconciliation.
    3.  Identify missing facts and unresolved questions.
    4.  Call only authorized evidence tools.
    5.  Retrieve relevant runbooks and historical cases.
    6.  Use metadata filters and hybrid lexical/dense retrieval.
    7.  Assemble an evidence-grounded prompt.
    8.  Request structured output from Gemini on Vertex AI.
    9.  Validate the output schema.
    10. Verify citation IDs against the actual evidence store.
    11. Reject unsupported case-specific claims.
    12. Apply action policy checks.
    13. Return the validated investigation and audit references.

Steps are numbered in comments below so the mapping to the spec stays
explicit. If no AI provider is given and Vertex AI can't be configured, step
8 is skipped and the report is built from the reconciliation result alone,
with `ai_used=False` and `source_mode=UNAVAILABLE` — never a fabricated
Gemini-shaped answer.
"""
from __future__ import annotations

from src.main.backend import audit
from src.main.backend.ai.exceptions import AIProviderUnavailable
from src.main.backend.ai.fake_provider import FakeAIProvider
from src.main.backend.ai.provider import InvestigationAIProvider
from src.main.backend.models import SourceMode
from src.main.backend.reconciliation import apply_reconciliation
from src.main.backend.retrieval.hybrid import retrieve_runbooks_hybrid, retrieve_similar_incidents
from src.main.backend.store import InMemoryStore
from src.main.backend.tools import schemas as tool_schemas
from src.main.backend.tools import service as tools

from .citation_verification import verify_and_strip_citations
from .schemas import InvestigationContext, InvestigationReport

REQUIRED_OUTPUT_FIELDS = (
    "summary", "recommended_next_action", "reasoning", "uncertainty_explanation",
    "unresolved_status",
)


def _default_provider() -> InvestigationAIProvider:
    """Vertex AI Gemini is the explicitly selected production provider
    (migrated off Google AI Studio). If Vertex is unavailable — ADC missing,
    model not configured, the call itself fails — this raises
    AIProviderUnavailable directly. It does NOT silently retry against the
    AI Studio API (GeminiFreeProvider still exists for local dev/testing,
    but is never auto-selected here). The orchestrator's own fallback path
    is the only place that decides to use the deterministic result instead."""
    from src.main.backend.ai.vertex_provider import VertexGeminiProvider  # lazy: optional dependency

    return VertexGeminiProvider()


def _coerce_unresolved_status(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in ("true", "unresolved", "yes", "1"):
            return True
        if token in ("false", "resolved", "no", "0"):
            return False
    raise ValueError(f"AI provider returned unrecognized unresolved_status value: {value!r}")


def _apply_policy_check(permitted_checks: list[str], recommended_next_action: str) -> tuple[str, bool]:
    """Step 12. recommended_next_action must be one of the reconciliation
    engine's own permitted_checks whenever that list is non-empty — this is
    what stops a provider (real or fake) from recommending something the
    deterministic rules didn't actually clear."""
    if not permitted_checks:
        return recommended_next_action, False
    if recommended_next_action in permitted_checks:
        return recommended_next_action, False
    return permitted_checks[0], True


def run_investigation(
    store: InMemoryStore, incident_id: str, provider: InvestigationAIProvider | None = None
) -> InvestigationReport:
    # Step 1
    incident = store.incidents[incident_id]

    # Step 2 (independent of any AI — see reconciliation/engine.py)
    reconciliation = apply_reconciliation(store, incident_id)
    # Step 3 is implicit: reconciliation.missing_evidence / unresolved_questions

    # Step 4: gather context only through the authorized tool functions,
    # not by reaching into the store directly.
    events = store.events_for_incident(incident_id)  # SourceEvent has no dedicated tool; read-only, same data find_payment_attempt/fetch_payment_status expose piecemeal
    evidence = tools.retrieve_bank_evidence(
        store, tool_schemas.RetrieveBankEvidenceInput(incident_id=incident_id)
    ).records
    # retrieve_bank_evidence only returns BANK_RECORD evidence by design (tool contract);
    # the orchestrator also needs the incident's other evidence types for a full picture.
    all_evidence = store.evidence_for_incident(incident_id)
    notifications = (
        tools.inspect_notification_records(
            store, tool_schemas.InspectNotificationRecordsInput(payment_attempt_id=incident.payment_attempt_id)
        ).notifications
        if incident.payment_attempt_id else []
    )

    # Step 5 + 6: runbooks and similar cases via hybrid (lexical + dense-proxy) retrieval.
    scored_runbooks = retrieve_runbooks_hybrid(store, reconciliation.classification.value)
    runbooks = [sr.runbook for sr in scored_runbooks]
    similar = retrieve_similar_incidents(
        store, incident, classification_filter=reconciliation.classification.value
    )

    # Step 7: assemble the typed context (doubles as the prompt source).
    context = InvestigationContext(
        incident=incident, reconciliation=reconciliation, events=events,
        evidence=all_evidence, notifications=notifications, runbooks=runbooks,
        similar_case_ids=[s.incident.incident_id for s in similar],
    )

    # Step 8: call the AI provider. Fall back honestly if unavailable.
    active_provider = provider
    ai_used = True
    if active_provider is None:
        try:
            active_provider = _default_provider()
        except AIProviderUnavailable as exc:
            audit.record(
                store, incident_id=incident_id, actor_id="investigation_orchestrator",
                event_type="AI_PROVIDER_UNAVAILABLE", result=str(exc),
            )
            active_provider = None
            ai_used = False

    if active_provider is not None:
        try:
            raw = active_provider.generate_investigation(context)
            model_identifier = active_provider.model_identifier
            source_mode = SourceMode.LIVE if active_provider.source_mode == "LIVE" else SourceMode.SIMULATED
        except AIProviderUnavailable as exc:
            audit.record(
                store, incident_id=incident_id, actor_id="investigation_orchestrator",
                event_type="AI_PROVIDER_UNAVAILABLE", result=str(exc),
            )
            active_provider = None
            ai_used = False

    if active_provider is None:
        # Deterministic fallback: still uses FakeAIProvider's synthesis logic
        # (pure function of reconciliation, no model call) so the shape of
        # the report is identical, but it is explicitly marked UNAVAILABLE —
        # not LIVE and not even the test-grade SIMULATED label — so the UI
        # can show "AI was unavailable; this is the deterministic fallback."
        raw = FakeAIProvider().generate_investigation(context)
        model_identifier = "none (deterministic fallback)"
        source_mode = SourceMode.UNAVAILABLE
        ai_used = False

    # Step 9: validate the output schema — every required field must be present.
    missing = [f for f in REQUIRED_OUTPUT_FIELDS if f not in raw]
    if missing:
        raise ValueError(f"AI provider output missing required fields: {missing}")

    # Gemini's JSON mode isn't given a typed schema, just a field-name list, so
    # it sometimes returns unresolved_status as a word ("RESOLVED") instead of
    # a boolean (observed live, not hypothetical) — coerce at this AI-output
    # boundary rather than letting Pydantic reject the whole report.
    raw["unresolved_status"] = _coerce_unresolved_status(raw["unresolved_status"])

    # Step 10 + 11: verify citations; strip and report anything unsupported.
    allowed_ids = context.allowed_citation_ids()
    valid_citations, removed_citations = verify_and_strip_citations(
        raw.get("citation_ids", []), allowed_ids,
    )
    valid_supporting, _ = verify_and_strip_citations(raw.get("supporting_evidence", []), allowed_ids)
    valid_contradicting, _ = verify_and_strip_citations(raw.get("contradicting_evidence", []), allowed_ids)

    # Step 12: policy check on the recommended action.
    safe_action, overridden = _apply_policy_check(
        reconciliation.permitted_checks, raw["recommended_next_action"],
    )

    report = InvestigationReport(
        incident_id=incident_id,
        summary=raw["summary"],
        confirmed_facts=raw.get("confirmed_facts", []),
        competing_hypotheses=raw.get("competing_hypotheses", []),
        supporting_evidence=valid_supporting,
        contradicting_evidence=valid_contradicting,
        missing_evidence=raw.get("missing_evidence", []),
        recommended_checks=raw.get("recommended_checks", []),
        recommended_next_action=safe_action,
        reasoning=raw["reasoning"],
        uncertainty_explanation=raw["uncertainty_explanation"],
        citation_ids=valid_citations,
        unresolved_status=raw["unresolved_status"],
        ai_used=ai_used,
        source_mode=source_mode,
        model_identifier=model_identifier,
        unsupported_claims_removed=removed_citations,
        policy_override_applied=overridden,
        raw_provider_output=raw,
    )

    # Step 13: audit trail.
    audit.record(
        store, incident_id=incident_id, actor_id="investigation_orchestrator",
        event_type="INVESTIGATION_RUN", result=reconciliation.classification.value,
        metadata={
            "ai_used": ai_used, "source_mode": source_mode.value,
            "model_identifier": model_identifier,
            "unsupported_claims_removed": len(removed_citations),
            "policy_override_applied": overridden,
        },
    )
    return report
