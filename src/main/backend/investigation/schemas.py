"""Structured output contract for the investigation pipeline (spec section 8)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.main.backend.models import (
    EvidenceRecord,
    Incident,
    NotificationRecord,
    Runbook,
    SourceEvent,
    SourceMode,
)
from src.main.backend.reconciliation import ReconciliationResult


class InvestigationContext(BaseModel):
    """Everything assembled for the prompt (step 7) before calling the AI
    provider (step 8). Kept as a typed object, not a raw string, so the fake
    and real providers both consume the same structured input."""

    incident: Incident
    reconciliation: ReconciliationResult
    events: list[SourceEvent] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    notifications: list[NotificationRecord] = Field(default_factory=list)
    runbooks: list[Runbook] = Field(default_factory=list)
    similar_case_ids: list[str] = Field(default_factory=list)

    def allowed_citation_ids(self) -> set[str]:
        """The only IDs a citation is allowed to point at: this incident's own
        evidence, plus the runbooks retrieved for it. Nothing else — not other
        incidents' evidence, not invented IDs."""
        return {e.evidence_id for e in self.evidence} | {rb.runbook_id for rb in self.runbooks}

    def to_prompt_text(self) -> str:
        """Plain-text rendering used by the real Gemini provider. The fake
        provider ignores this and reasons over the structured fields directly."""
        lines = [
            f"Incident {self.incident.incident_id}: {self.incident.title}",
            f"Complaint: {self.incident.complaint}",
            f"Amount: {self.incident.amount} {self.incident.currency}",
            f"Deterministic reconciliation classification: {self.reconciliation.classification.value}",
            f"Confirmed facts: {self.reconciliation.confirmed_facts}",
            f"Conflicts: {self.reconciliation.conflicts}",
            f"Missing evidence: {self.reconciliation.missing_evidence}",
            f"Permitted checks: {self.reconciliation.permitted_checks}",
            f"Action restrictions: {self.reconciliation.action_restrictions}",
            "Evidence available (cite ONLY these evidence_ids):",
        ]
        for e in self.evidence:
            lines.append(f"  - {e.evidence_id} [{e.source_system}] {e.title}: {e.content}")
        lines.append("Runbooks available (cite ONLY these runbook_ids):")
        for rb in self.runbooks:
            lines.append(f"  - {rb.runbook_id}: {rb.title}")
        return "\n".join(lines)


class InvestigationReport(BaseModel):
    incident_id: str
    summary: str
    confirmed_facts: list[str] = Field(default_factory=list)
    competing_hypotheses: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    recommended_next_action: str
    reasoning: str
    uncertainty_explanation: str
    citation_ids: list[str] = Field(default_factory=list)
    unresolved_status: bool

    # Provenance — never hidden from the caller, per spec section 8's
    # requirement that fallback use be clearly visible, not silent.
    ai_used: bool
    source_mode: SourceMode
    model_identifier: str

    # Populated by citation verification (step 10-11), not by the provider.
    unsupported_claims_removed: list[str] = Field(default_factory=list)
    policy_override_applied: bool = False
    raw_provider_output: dict[str, Any] = Field(default_factory=dict)
