"""Phase 2 acceptance tests: deterministic reconciliation engine.

Two layers:
1. Hand-crafted minimal cases, one per rule (spec: "write unit tests for
   every rule, including contradictory and incomplete records").
2. A full cross-check: every incident the Phase 1 generator produced should
   reconcile to the classification its ground truth says it should.
"""
from datetime import datetime, timezone

from src.main.backend.models import (
    Incident,
    MerchantOrder,
    NotificationRecord,
    OrderStatus,
    PaymentAttempt,
    ProcessingStatus,
    DeliveryStatus,
    ReconciliationStatus,
    SourceEvent,
    VerificationStatus,
)
from src.main.backend.reconciliation.engine import reconcile
from src.main.backend.store import load_default_store

NOW = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)


def _incident(**overrides) -> Incident:
    base = dict(
        incident_id="INC-TEST", created_at=NOW, updated_at=NOW, title="t",
        complaint="c", amount="100", merchant_id="IRCTC",
    )
    base.update(overrides)
    return Incident(**base)


def test_rule1_abstains_on_unresolved_marker():
    incident = _incident()
    events = [SourceEvent(
        event_id="E1", incident_id=incident.incident_id, source_system="gw",
        event_type="X", event_time=NOW, ingested_at=NOW, source_status="UNKNOWN",
        normalized_status="UNRESOLVED",
    )]
    result = reconcile(incident, None, None, events, [], [])
    assert result.classification == ReconciliationStatus.INSUFFICIENT_EVIDENCE
    assert "R1_insufficient_evidence_abstain" in result.rules_applied


def test_rule2_flags_duplicate_on_multiple_transaction_refs():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T2", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    events = [
        SourceEvent(event_id="E1", incident_id=incident.incident_id, transaction_ref="T1",
                    source_system="gw", event_type="X", event_time=NOW, ingested_at=NOW,
                    source_status="FAILED", normalized_status="FAILED"),
        SourceEvent(event_id="E2", incident_id=incident.incident_id, transaction_ref="T2",
                    source_system="gw", event_type="X", event_time=NOW, ingested_at=NOW,
                    source_status="SUCCESS", normalized_status="CONFIRMED"),
    ]
    result = reconcile(incident, pa, None, events, [], [])
    assert result.classification == ReconciliationStatus.POSSIBLE_DUPLICATE
    assert "R2_duplicate_not_separate_event" in result.rules_applied


def test_rule2_flags_duplicate_notifications():
    incident = _incident(payment_attempt_id="PA1")
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    notifications = [
        NotificationRecord(notification_id="N1", payment_attempt_id="PA1",
                            destination_system="m", delivery_status=DeliveryStatus.DELIVERED,
                            processing_status=ProcessingStatus.PROCESSED, created_at=NOW),
        NotificationRecord(notification_id="N2", payment_attempt_id="PA1",
                            destination_system="m", delivery_status=DeliveryStatus.DELIVERED,
                            processing_status=ProcessingStatus.REJECTED, created_at=NOW),
    ]
    result = reconcile(incident, pa, None, [], [], notifications)
    assert result.classification == ReconciliationStatus.POSSIBLE_DUPLICATE


def test_rule3_flags_conflicting_sources_same_transaction_ref():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    events = [
        SourceEvent(event_id="E1", incident_id=incident.incident_id, transaction_ref="T1",
                    source_system="gw", event_type="X", event_time=NOW, ingested_at=NOW,
                    source_status="SUCCESS", normalized_status="CONFIRMED"),
        SourceEvent(event_id="E2", incident_id=incident.incident_id, transaction_ref="T1",
                    source_system="bank", event_type="X", event_time=NOW, ingested_at=NOW,
                    source_status="TIMEOUT", normalized_status="CONFLICTED"),
    ]
    result = reconcile(incident, pa, None, events, [], [])
    assert result.classification == ReconciliationStatus.STATUS_MISMATCH
    assert "R3_conflicting_sources_stay_visible" in result.rules_applied


def test_rule3_does_not_confuse_not_found_with_a_conflict():
    """A missing merchant order is not proof of a failed bank transaction —
    NOT_FOUND must not be treated as a disagreeing status."""
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    events = [
        SourceEvent(event_id="E1", incident_id=incident.incident_id, transaction_ref="T1",
                    source_system="bank", event_type="X", event_time=NOW, ingested_at=NOW,
                    source_status="DEBIT_SUCCESS", normalized_status="DEBITED"),
        SourceEvent(event_id="E2", incident_id=incident.incident_id, transaction_ref="T1",
                    source_system="merchant", event_type="ORDER_LOOKUP", event_time=NOW,
                    ingested_at=NOW, source_status="NOT_FOUND", normalized_status="NOT_FOUND"),
    ]
    result = reconcile(incident, pa, None, events, [], [])
    assert result.classification != ReconciliationStatus.STATUS_MISMATCH
    assert result.classification == ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING


def test_rule3_flags_order_cancelled_after_payment_success():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    order = MerchantOrder(order_id="O1", merchant_id="IRCTC", payment_attempt_id="PA1",
                           amount="100", order_status=OrderStatus.CANCELLED,
                           created_at=NOW, updated_at=NOW, source_system="m")
    result = reconcile(incident, pa, order, [], [], [])
    assert result.classification == ReconciliationStatus.STATUS_MISMATCH


def test_rule4_refund_requested_stays_unverified_not_refunded():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    events = [SourceEvent(event_id="E1", incident_id=incident.incident_id, transaction_ref="T1",
                           source_system="support", event_type="REFUND_REQUESTED",
                           event_time=NOW, ingested_at=NOW, source_status="REQUESTED",
                           normalized_status="REFUND_REQUESTED")]
    result = reconcile(incident, pa, None, events, [], [])
    assert result.classification == ReconciliationStatus.REVERSAL_UNVERIFIED
    assert "reversal_or_refund_confirmation" in result.missing_evidence


def test_rule4_failed_payment_without_reversal_confirmation():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="FAILED",
                         source_system="gw")
    result = reconcile(incident, pa, None, [], [], [])
    assert result.classification == ReconciliationStatus.REVERSAL_UNVERIFIED


def test_rule4_does_not_fire_once_reversal_is_confirmed():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="FAILED",
                         source_system="gw")
    events = [SourceEvent(event_id="E1", incident_id=incident.incident_id, transaction_ref="T1",
                           source_system="bank", event_type="REVERSAL_CONFIRMED",
                           event_time=NOW, ingested_at=NOW, source_status="REVERSED",
                           normalized_status="REVERSED")]
    result = reconcile(incident, pa, None, events, [], [])
    assert result.classification != ReconciliationStatus.REVERSAL_UNVERIFIED


def test_rule5_debit_alone_does_not_prove_merchant_confirmation():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    result = reconcile(incident, pa, None, [], [], [])  # no merchant_order at all
    assert result.classification == ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING
    assert "merchant_order_record" in result.missing_evidence


def test_rule5_missing_callback_is_not_proof_of_failure():
    """A payment that succeeded but whose notification was never processed
    must land on MERCHANT_CONFIRMATION_MISSING, not a failure-like status."""
    incident = _incident(payment_attempt_id="PA1")
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    order = MerchantOrder(order_id="O1", merchant_id="IRCTC", payment_attempt_id="PA1",
                           amount="100", order_status=OrderStatus.PENDING,
                           created_at=NOW, updated_at=NOW, source_system="m")
    notifications = [NotificationRecord(
        notification_id="N1", payment_attempt_id="PA1", destination_system="m",
        delivery_status=DeliveryStatus.FAILED, processing_status=ProcessingStatus.NOT_PROCESSED,
        created_at=NOW,
    )]
    result = reconcile(incident, pa, order, [], [], notifications)
    assert result.classification == ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING


def test_rule6_pending_stays_pending():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="PENDING",
                         source_system="gw")
    result = reconcile(incident, pa, None, [], [], [])
    assert result.classification == ReconciliationStatus.PENDING
    assert "do_not_conclude_success_or_failure_while_pending" in result.action_restrictions


def test_rule7_confirmed_when_both_sides_agree():
    incident = _incident()
    pa = PaymentAttempt(payment_attempt_id="PA1", transaction_ref="T1", amount="100",
                         payment_method="UPI", created_at=NOW, provider_status="SUCCESS",
                         source_system="gw")
    order = MerchantOrder(order_id="O1", merchant_id="IRCTC", payment_attempt_id="PA1",
                           amount="100", order_status=OrderStatus.CONFIRMED,
                           created_at=NOW, updated_at=NOW, source_system="m")
    result = reconcile(incident, pa, order, [], [], [])
    assert result.classification == ReconciliationStatus.CONFIRMED


def test_rule8_fallback_when_nothing_else_matches():
    incident = _incident()
    result = reconcile(incident, None, None, [], [], [])  # no payment attempt at all
    assert result.classification == ReconciliationStatus.UNRESOLVED
    assert "R8_unresolved_fallback" in result.rules_applied


# -- full cross-check against the Phase 1 generator -------------------------

def test_every_generated_incident_reconciles_to_its_ground_truth_classification():
    store = load_default_store()
    assert store.incidents, "expected synthetic data to be generated already"
    mismatches = []
    for incident_id, incident in store.incidents.items():
        gt = store.ground_truth.get(incident_id)
        if gt is None:
            continue
        pa = store.payment_attempts.get(incident.payment_attempt_id) if incident.payment_attempt_id else None
        order = store.merchant_order_for(
            payment_attempt_id=incident.payment_attempt_id, transaction_ref=incident.transaction_ref,
        )
        events = store.events_for_incident(incident_id)
        evidence = store.evidence_for_incident(incident_id)
        notifications = (
            store.notifications_for_payment_attempt(incident.payment_attempt_id)
            if incident.payment_attempt_id else []
        )
        result = reconcile(incident, pa, order, events, evidence, notifications)
        if result.classification != gt.expected_reconciliation_status:
            mismatches.append(
                f"{incident_id} ({gt.scenario_category}): engine={result.classification.value} "
                f"expected={gt.expected_reconciliation_status.value} rules={result.rules_applied}"
            )
    assert not mismatches, "Reconciliation mismatches:\n" + "\n".join(mismatches)
