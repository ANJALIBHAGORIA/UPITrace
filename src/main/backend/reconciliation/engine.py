"""Deterministic reconciliation engine (spec section 5).

Runs independently of any LLM. Given an incident and its linked records, it
returns a classification plus the evidence/reasoning behind it. Rules are
checked in a fixed priority order (see `reconcile`); the first rule that
matches wins and the rest are not evaluated for classification purposes
(though confirmed_facts/missing_evidence are still collected broadly).

Each rule below maps directly to one of the eight bullet points in spec
section 5 ("A missing callback is not proof of failure.", etc.) — the mapping
is called out in each function's docstring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.main.backend.models import (
    EvidenceRecord,
    Incident,
    MerchantOrder,
    NotificationRecord,
    OrderStatus,
    PaymentAttempt,
    ProcessingStatus,
    ReconciliationStatus,
    SourceEvent,
)
from src.main.backend.store import InMemoryStore

# Statuses that represent "no record found", never a disagreement about a
# real outcome. Excluded from status-mismatch detection on purpose (spec: "A
# missing merchant order is not proof of a failed bank transaction").
_ABSENCE_STATUSES = {"NOT_FOUND"}

# Deliberate marker the generator uses for genuinely ambiguous cases. Any
# other "unusual" status string is treated as a real (if odd) status, not as
# a request to abstain — abstention must be an explicit signal, not a guess.
_ABSTAIN_MARKER = "UNRESOLVED"


class ReconciliationResult(BaseModel):
    incident_id: str
    classification: ReconciliationStatus
    confirmed_facts: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    permitted_checks: list[str] = Field(default_factory=list)
    action_restrictions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)


def _group_events_by_transaction_ref(events: list[SourceEvent]) -> dict[Optional[str], list[SourceEvent]]:
    groups: dict[Optional[str], list[SourceEvent]] = {}
    for e in events:
        groups.setdefault(e.transaction_ref, []).append(e)
    return groups


def reconcile(
    incident: Incident,
    payment_attempt: Optional[PaymentAttempt],
    merchant_order: Optional[MerchantOrder],
    events: list[SourceEvent],
    evidence: list[EvidenceRecord],
    notifications: list[NotificationRecord],
) -> ReconciliationResult:
    confirmed_facts: list[str] = []
    conflicts: list[str] = []
    missing_evidence: list[str] = []
    unresolved_questions: list[str] = []
    permitted_checks: list[str] = []
    action_restrictions: list[str] = []
    rules_applied: list[str] = []
    evidence_ids = [e.evidence_id for e in evidence]

    provider_status = payment_attempt.provider_status if payment_attempt else None

    if provider_status == "SUCCESS":
        confirmed_facts.append("payment_settled_at_gateway")
    if merchant_order and merchant_order.order_status == OrderStatus.CONFIRMED:
        confirmed_facts.append("merchant_order_confirmed")

    tx_groups = _group_events_by_transaction_ref(events)
    distinct_tx_refs = [ref for ref in tx_groups if ref is not None]

    # --- Rule R1: "If evidence is insufficient, abstain and identify what is
    # missing." Checked first — ambiguity takes priority over every other
    # classification so the engine never guesses past a genuine evidence gap.
    abstain_events = [e for e in events if e.normalized_status == _ABSTAIN_MARKER]
    gap_evidence = [e for e in evidence if "gap_minutes" in (e.metadata or {})]
    if abstain_events or gap_evidence:
        rules_applied.append("R1_insufficient_evidence_abstain")
        missing_evidence.append("authoritative_status_unavailable")
        if gap_evidence:
            unresolved_questions.append(
                f"Event log gap of {gap_evidence[0].metadata.get('gap_minutes')} minutes before next known event."
            )
        permitted_checks.append("request_additional_evidence")
        action_restrictions.append("no_definitive_customer_resolution_until_evidence_gap_closed")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.INSUFFICIENT_EVIDENCE,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R2: "A duplicate record must not be counted as a separate
    # financial event without evidence." Multiple transaction_refs for one
    # incident, or multiple notifications for one payment attempt, are
    # flagged as possible duplicates rather than independent events.
    duplicate_notifications = (
        len(notifications) > 1
        and payment_attempt is not None
        and len({n.notification_id for n in notifications}) > 1
    )
    if len(distinct_tx_refs) > 1 or duplicate_notifications:
        rules_applied.append("R2_duplicate_not_separate_event")
        conflicts.append("multiple_candidate_events_for_same_underlying_payment")
        unresolved_questions.append("Is this a genuine retry/duplicate, or two independent transactions?")
        permitted_checks.append("confirm_single_underlying_settlement")
        action_restrictions.append("no_refund_or_second_charge_until_duplicate_confirmed_or_ruled_out")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.POSSIBLE_DUPLICATE,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R3: "Conflicting sources must remain visible." Two forms:
    # (a) events sharing one transaction_ref disagree on normalized_status
    #     (absence markers like NOT_FOUND are excluded — see module docstring);
    # (b) the merchant order was expired/cancelled yet the payment succeeded.
    status_conflict = False
    for ref, group in tx_groups.items():
        statuses = {e.normalized_status for e in group if e.normalized_status not in _ABSENCE_STATUSES}
        if len(statuses) > 1:
            status_conflict = True
            conflicts.append(f"sources disagree on outcome for {ref}: {sorted(statuses)}")

    order_payment_conflict = (
        merchant_order is not None
        and merchant_order.order_status in (OrderStatus.EXPIRED, OrderStatus.CANCELLED)
        and provider_status == "SUCCESS"
    )
    if order_payment_conflict:
        conflicts.append(
            f"merchant order is {merchant_order.order_status.value} but payment settled successfully"
        )

    if status_conflict or order_payment_conflict:
        rules_applied.append("R3_conflicting_sources_stay_visible")
        unresolved_questions.append("Which source reflects the true final outcome?")
        permitted_checks.append("fetch_latest_authoritative_status_from_each_source")
        action_restrictions.append("no_action_until_conflict_is_resolved_or_explicitly_overridden")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.STATUS_MISMATCH,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R4: "Do not invent reversal or settlement outcomes." A refund
    # request or a failed payment, with no confirming reversal evidence, stays
    # unverified rather than being presented as refunded/reversed.
    refund_requested = any(e.event_type == "REFUND_REQUESTED" for e in events)
    reversal_confirmed = any(e.event_type in ("REVERSAL_CONFIRMED", "REFUND_CONFIRMED") for e in events)
    if refund_requested or (provider_status == "FAILED" and not reversal_confirmed):
        rules_applied.append("R4_no_invented_reversal_outcome")
        missing_evidence.append("reversal_or_refund_confirmation")
        unresolved_questions.append("Has the reversal/refund actually settled yet?")
        permitted_checks.append("query_reversal_status")
        action_restrictions.append("do_not_tell_customer_refund_is_complete_without_confirmation")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.REVERSAL_UNVERIFIED,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R5: "A debit record alone does not prove merchant confirmation
    # or beneficiary credit." / "A missing merchant order is not proof of a
    # failed bank transaction." / "A missing callback is not proof of
    # failure." All three collapse to: payment succeeded, but merchant-side
    # confirmation is absent, unconfirmed, or not yet processed.
    notification_not_processed = any(n.processing_status == ProcessingStatus.NOT_PROCESSED for n in notifications)
    merchant_confirmation_absent = merchant_order is None or merchant_order.order_status in (
        OrderStatus.NOT_FOUND, OrderStatus.PENDING,
    )
    if provider_status == "SUCCESS" and (merchant_confirmation_absent or notification_not_processed):
        rules_applied.append("R5_debit_or_notification_not_proof_of_confirmation")
        if merchant_order is None:
            missing_evidence.append("merchant_order_record")
        elif merchant_order.order_status == OrderStatus.NOT_FOUND:
            missing_evidence.append("merchant_order_record")
        if notification_not_processed:
            missing_evidence.append("notification_processing_confirmation")
        unresolved_questions.append("Has the merchant side actually registered this payment yet?")
        permitted_checks.append("recheck_merchant_order_status")
        action_restrictions.append("do_not_declare_payment_failed_solely_due_to_missing_merchant_confirmation")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R6: "A pending provider status must remain pending unless
    # sufficient evidence supports a transition."
    if provider_status == "PENDING":
        rules_applied.append("R6_pending_stays_pending")
        unresolved_questions.append("Will this settle, fail, or remain pending?")
        permitted_checks.append("recheck_after_wait_window")
        action_restrictions.append("do_not_conclude_success_or_failure_while_pending")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.PENDING,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R7: everything corroborates — payment succeeded and the
    # merchant order is confirmed, with no conflicts or gaps surfaced above.
    if provider_status == "SUCCESS" and merchant_order is not None and merchant_order.order_status == OrderStatus.CONFIRMED:
        rules_applied.append("R7_confirmed_when_fully_corroborated")
        return ReconciliationResult(
            incident_id=incident.incident_id,
            classification=ReconciliationStatus.CONFIRMED,
            confirmed_facts=confirmed_facts, conflicts=conflicts,
            missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
            permitted_checks=permitted_checks, action_restrictions=action_restrictions,
            evidence_ids=evidence_ids, rules_applied=rules_applied,
        )

    # --- Rule R8: nothing above matched — say so explicitly rather than
    # defaulting to a specific-sounding classification we can't support.
    rules_applied.append("R8_unresolved_fallback")
    unresolved_questions.append("No rule matched this evidence combination; needs manual review.")
    permitted_checks.append("manual_review")
    action_restrictions.append("no_automated_action")
    return ReconciliationResult(
        incident_id=incident.incident_id,
        classification=ReconciliationStatus.UNRESOLVED,
        confirmed_facts=confirmed_facts, conflicts=conflicts,
        missing_evidence=missing_evidence, unresolved_questions=unresolved_questions,
        permitted_checks=permitted_checks, action_restrictions=action_restrictions,
        evidence_ids=evidence_ids, rules_applied=rules_applied,
    )


def apply_reconciliation(store: InMemoryStore, incident_id: str) -> ReconciliationResult:
    """Looks up everything `reconcile` needs from the store, runs it, and
    persists the resulting classification back onto the incident."""
    incident = store.incidents[incident_id]
    payment_attempt = (
        store.payment_attempts.get(incident.payment_attempt_id) if incident.payment_attempt_id else None
    )
    merchant_order = store.merchant_order_for(
        payment_attempt_id=incident.payment_attempt_id, transaction_ref=incident.transaction_ref,
    )
    events = store.events_for_incident(incident_id)
    evidence = store.evidence_for_incident(incident_id)
    notifications = (
        store.notifications_for_payment_attempt(incident.payment_attempt_id)
        if incident.payment_attempt_id else []
    )

    result = reconcile(incident, payment_attempt, merchant_order, events, evidence, notifications)

    incident.reconciliation_status = result.classification
    incident.updated_at = datetime.now(timezone.utc)
    store.incidents[incident_id] = incident
    return result
