"""Deterministic synthetic data generator for UPITrace (spec section 4).

Usage:
    python -m src.main.backend.scripts.generate_synthetic_data [--seed 42]

Writes:
    src/main/backend/data/synthetic/incidents.json       (+ payment_attempts,
        merchant_orders, source_events, evidence_records, notification_records,
        runbooks.json)
    src/main/backend/data/evaluation/ground_truth.json    (kept separate on
        purpose — see docs/architecture.md)

Each of the 12 required scenario categories gets 3 incidents (36 total, >= 30),
built by a dedicated `_build_<category>` function so each intentional
contradiction is explicit and documented at its source, rather than emerging
from shared generic logic.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from src.main.backend.models import (
    DeliveryStatus,
    EvidenceRecord,
    EvaluationGroundTruth,
    Incident,
    IncidentStatus,
    MerchantOrder,
    NotificationRecord,
    OrderStatus,
    PaymentAttempt,
    ProcessingStatus,
    ReconciliationStatus,
    Runbook,
    SourceEvent,
    SourceMode,
    VerificationStatus,
)

BASE_TIME = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
MERCHANTS = [
    "IRCTC", "BigBasket", "Zomato", "BookMyShow", "Flipkart", "Swiggy",
    "Myntra", "Amazon", "MakeMyTrip", "PharmEasy", "Ola",
]
TIME_SPREAD_MINUTES = 15  # gap between consecutive incidents' anchors
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
SYNTHETIC_DIR = DATA_ROOT / "synthetic"
EVALUATION_DIR = DATA_ROOT / "evaluation"


@dataclass
class Bundle:
    """Everything produced for one incident."""

    incident: Incident
    payment_attempt: Optional[PaymentAttempt] = None
    merchant_order: Optional[MerchantOrder] = None
    events: list[SourceEvent] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    notifications: list[NotificationRecord] = field(default_factory=list)
    ground_truth: Optional[EvaluationGroundTruth] = None


class IdFactory:
    """Stable, human-readable IDs derived from a running counter (reproducible
    given a fixed seed and generation order)."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]:04d}"


# Mutable anchor, set once per incident before its builder runs (see
# `generate()`). Lets every builder keep writing small relative offsets like
# _ts(0), _ts(2) for "within this incident's timeline" while still landing
# each incident at a distinct, spread-out point in history — without having
# to thread an index through every one of the ~40+ _ts() call sites.
_anchor_minutes = [0.0]


def _ts(minutes: float) -> datetime:
    return BASE_TIME + timedelta(minutes=_anchor_minutes[0] + minutes)


# ---------------------------------------------------------------------------
# One builder per scenario category. Each documents its deliberate
# contradiction/gap in its docstring, per spec section 4's requirement that
# intentional contradictions be deliberate and documented.
# ---------------------------------------------------------------------------


def _build_both_confirmed(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """No contradiction: control case where every source agrees."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([199, 499, 2499, 899]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    order_id = ids.next("ORD")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, merchant_order_ref=order_id,
        amount=amount, payment_method="UPI", created_at=_ts(0),
        provider_status="SUCCESS", source_system="payment_gateway",
        correlation_ids=[txn_ref],
    )
    order = MerchantOrder(
        order_id=order_id, merchant_id=merchant, payment_attempt_id=pa_id,
        transaction_ref=txn_ref, amount=amount, order_status=OrderStatus.CONFIRMED,
        created_at=_ts(1), updated_at=_ts(2), source_system=f"{merchant}_portal",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_SUCCESS",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="SUCCESS",
                    normalized_status="CONFIRMED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system=f"{merchant}_portal", event_type="ORDER_CONFIRMED",
                    event_time=_ts(2), ingested_at=_ts(2.1), source_status="CONFIRMED",
                    normalized_status="CONFIRMED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Gateway success response", content="Payment settled successfully.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(3), updated_at=_ts(3),
        title=f"Payment to {merchant} #{idx}", complaint="No issue reported; control case.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.RESOLVED,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="BOTH_CONFIRMED",
        expected_reconciliation_status=ReconciliationStatus.CONFIRMED,
        expected_safe_next_action="None — payment and order both confirmed.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, order, events, evidence, [], gt)


def _build_debit_no_merchant_confirm(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: payer debit is confirmed but the merchant has no matching
    order yet. A debit record alone must not be read as merchant confirmation."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([349, 1299, 2999]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="SUCCESS",
        source_system="payment_gateway", correlation_ids=[txn_ref],
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payer_bank", event_type="DEBIT_CONFIRMED",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="DEBIT_SUCCESS",
                    normalized_status="DEBITED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system=f"{merchant}_portal", event_type="ORDER_LOOKUP",
                    event_time=_ts(5), ingested_at=_ts(5.1), source_status="NOT_FOUND",
                    normalized_status="NOT_FOUND",
                    verification_status=VerificationStatus.UNVERIFIED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="BANK_RECORD", source_system="payer_bank",
                        title="Debit confirmation", content="Debit of amount confirmed by bank.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.VERIFIED),
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="MERCHANT_ORDER", source_system=f"{merchant}_portal",
                        title="Order lookup result", content="No matching order found for this reference.",
                        ingested_at=_ts(5.1), verification_status=VerificationStatus.UNVERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(6), updated_at=_ts(6),
        title=f"Debited but {merchant} order missing #{idx}",
        complaint="Money was debited but I can't see my order on the merchant app.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="DEBIT_NO_MERCHANT_CONFIRM",
        expected_reconciliation_status=ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING,
        expected_safe_next_action="Wait and recheck merchant order status before raising a dispute.",
        is_resolvable=True,
        notes="Debit confirmed != merchant confirmation. NOT_FOUND != order never existed.",
    )
    return Bundle(incident, pa, None, events, evidence, [], gt)


def _build_both_pending(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """No contradiction, but no resolution either: both provider and merchant
    report PENDING. Must not be upgraded to CONFIRMED or FAILED prematurely."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([599, 1499]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    order_id = ids.next("ORD")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, merchant_order_ref=order_id,
        amount=amount, payment_method="UPI", created_at=_ts(0),
        provider_status="PENDING", source_system="payment_gateway",
    )
    order = MerchantOrder(
        order_id=order_id, merchant_id=merchant, payment_attempt_id=pa_id,
        transaction_ref=txn_ref, amount=amount, order_status=OrderStatus.PENDING,
        created_at=_ts(1), updated_at=_ts(1), source_system=f"{merchant}_portal",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_PENDING",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="PENDING",
                    normalized_status="PENDING", amount=amount),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Gateway pending status", content="Transaction still processing.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.UNVERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(2), updated_at=_ts(2),
        title=f"Payment to {merchant} stuck pending #{idx}",
        complaint="Payment shows pending for a while now.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.AWAITING_EVIDENCE,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="BOTH_PENDING",
        expected_reconciliation_status=ReconciliationStatus.PENDING,
        expected_safe_next_action="Recheck after a reasonable wait window; do not conclude success or failure.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, order, events, evidence, [], gt)


def _build_missing_notification(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: payment succeeded but the merchant notification was never
    created/sent at all (distinct from 'delivered but not processed')."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([799, 2199]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="SUCCESS",
        source_system="payment_gateway",
    )
    notifications = [
        NotificationRecord(
            notification_id=ids.next("NOTIF"), payment_attempt_id=pa_id,
            destination_system=f"{merchant}_webhook",
            delivery_status=DeliveryStatus.FAILED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
            created_at=_ts(0.2),
        ),
    ]
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_SUCCESS",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="SUCCESS",
                    normalized_status="CONFIRMED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="NOTIFICATION_LOG", source_system=f"{merchant}_webhook",
                        title="Webhook delivery failure", content="No successful delivery attempt recorded.",
                        ingested_at=_ts(0.2), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(1), updated_at=_ts(1),
        title=f"{merchant} never notified of payment #{idx}",
        complaint="Paid successfully but merchant has no record of it.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="MISSING_NOTIFICATION",
        expected_reconciliation_status=ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING,
        expected_safe_next_action="Retrigger merchant notification before assuming payment failure.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, None, events, evidence, notifications, gt)


def _build_notification_delivered_not_processed(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: the webhook was delivered successfully, but the merchant
    system never processed it into an order update. Delivery != processing."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([449, 999]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    order_id = ids.next("ORD")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, merchant_order_ref=order_id,
        amount=amount, payment_method="UPI", created_at=_ts(0),
        provider_status="SUCCESS", source_system="payment_gateway",
    )
    order = MerchantOrder(
        order_id=order_id, merchant_id=merchant, payment_attempt_id=pa_id,
        transaction_ref=txn_ref, amount=amount, order_status=OrderStatus.PENDING,
        created_at=_ts(1), updated_at=_ts(1), source_system=f"{merchant}_portal",
    )
    notifications = [
        NotificationRecord(
            notification_id=ids.next("NOTIF"), payment_attempt_id=pa_id,
            destination_system=f"{merchant}_webhook",
            delivery_status=DeliveryStatus.DELIVERED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
            created_at=_ts(0.2), delivered_at=_ts(0.4),
        ),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="NOTIFICATION_LOG", source_system=f"{merchant}_webhook",
                        title="Webhook delivered, order not updated",
                        content="HTTP 200 received by merchant; order status unchanged afterward.",
                        ingested_at=_ts(0.4), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(2), updated_at=_ts(2),
        title=f"{merchant} webhook delivered but order stuck #{idx}",
        complaint="Paid but order still shows pending.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="NOTIFICATION_DELIVERED_NOT_PROCESSED",
        expected_reconciliation_status=ReconciliationStatus.MERCHANT_CONFIRMATION_MISSING,
        expected_safe_next_action="Ask merchant to reprocess the delivered webhook payload.",
        is_resolvable=True,
        notes="Delivery success must not be conflated with processing success.",
    )
    return Bundle(incident, pa, order, [], evidence, notifications, gt)


def _build_provider_bank_conflict(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Direct contradiction: gateway says SUCCESS, bank says TIMEOUT. Both
    statuses must stay visible; neither is silently preferred."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([2499, 349]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="SUCCESS",
        source_system="payment_gateway",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_STATUS",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="SUCCESS",
                    normalized_status="CONFIRMED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payer_bank", event_type="PAYMENT_STATUS",
                    event_time=_ts(0.05), ingested_at=_ts(0.2), source_status="TIMEOUT",
                    normalized_status="CONFLICTED", amount=amount,
                    verification_status=VerificationStatus.CONFLICTED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Gateway: SUCCESS", content="Gateway reports settlement success.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.VERIFIED),
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="BANK_RECORD", source_system="payer_bank",
                        title="Bank: TIMEOUT", content="Bank reports a timeout for the same reference.",
                        ingested_at=_ts(0.2), verification_status=VerificationStatus.CONFLICTED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(1), updated_at=_ts(1),
        title=f"Conflicting status for {merchant} payment #{idx}",
        complaint="App says paid, bank statement shows a failed/timeout attempt.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="PROVIDER_BANK_CONFLICT",
        expected_reconciliation_status=ReconciliationStatus.STATUS_MISMATCH,
        expected_safe_next_action="Query the latest authoritative status from both sides before acting.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, None, events, evidence, [], gt)


def _build_duplicate_notification(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction risk: the same notification arrives twice. Must not be
    counted as two separate financial events."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([599, 1199]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="SUCCESS",
        source_system="payment_gateway",
    )
    notifications = [
        NotificationRecord(
            notification_id=ids.next("NOTIF"), payment_attempt_id=pa_id,
            destination_system=f"{merchant}_webhook", delivery_status=DeliveryStatus.DELIVERED,
            processing_status=ProcessingStatus.PROCESSED, created_at=_ts(0.2), delivered_at=_ts(0.3),
            processed_at=_ts(0.35),
        ),
        NotificationRecord(
            notification_id=ids.next("NOTIF"), payment_attempt_id=pa_id,
            destination_system=f"{merchant}_webhook", delivery_status=DeliveryStatus.DELIVERED,
            processing_status=ProcessingStatus.REJECTED, created_at=_ts(0.4), delivered_at=_ts(0.5),
        ),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="NOTIFICATION_LOG", source_system=f"{merchant}_webhook",
                        title="Duplicate webhook received",
                        content="Same payment reference notified twice; second attempt rejected as duplicate.",
                        ingested_at=_ts(0.5), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(1), updated_at=_ts(1),
        title=f"Duplicate notification for {merchant} order #{idx}",
        complaint="Worried I might have been charged or confirmed twice.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="DUPLICATE_NOTIFICATION",
        expected_reconciliation_status=ReconciliationStatus.POSSIBLE_DUPLICATE,
        expected_safe_next_action="Confirm single underlying payment before any customer-facing action.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, None, [], evidence, notifications, gt)


def _build_duplicate_payment_attempt(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction risk: two payment attempts with the same amount/merchant
    close in time — could be a genuine retry or an actual double-charge."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([999, 1499]))
    txn_ref_1 = ids.next("TXN")
    txn_ref_2 = ids.next("TXN")
    pa_id_1 = ids.next("PA")
    pa_id_2 = ids.next("PA")
    incident_id = ids.next("INC")

    pa1 = PaymentAttempt(
        payment_attempt_id=pa_id_1, transaction_ref=txn_ref_1, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="FAILED",
        source_system="payment_gateway",
    )
    pa2 = PaymentAttempt(
        payment_attempt_id=pa_id_2, transaction_ref=txn_ref_2, amount=amount,
        payment_method="UPI", created_at=_ts(0.5), provider_status="SUCCESS",
        source_system="payment_gateway", correlation_ids=[txn_ref_1],
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref_1,
                    source_system="payment_gateway", event_type="PAYMENT_FAILED",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="FAILED",
                    normalized_status="FAILED", amount=amount),
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref_2,
                    source_system="payment_gateway", event_type="PAYMENT_SUCCESS",
                    event_time=_ts(0.5), ingested_at=_ts(0.6), source_status="SUCCESS",
                    normalized_status="CONFIRMED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Two attempts, same amount", content="First attempt failed; retry succeeded.",
                        ingested_at=_ts(0.6), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(1), updated_at=_ts(1),
        title=f"Two payment attempts to {merchant} #{idx}",
        complaint="Not sure if I was charged once or twice.",
        transaction_ref=txn_ref_2, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id_2, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="DUPLICATE_PAYMENT_ATTEMPT",
        expected_reconciliation_status=ReconciliationStatus.POSSIBLE_DUPLICATE,
        expected_safe_next_action="Verify only one attempt actually debited funds before any refund.",
        is_resolvable=True,
    )
    # Store both attempts by returning pa2 as the "primary" one on the bundle;
    # pa1 still appears in evidence/events for the timeline.
    bundle = Bundle(incident, pa2, None, events, evidence, [], gt)
    bundle.evidence.append(
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="First (failed) attempt record", content=f"Attempt {pa_id_1} recorded as FAILED.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.VERIFIED)
    )
    return bundle


def _build_refund_requested_unverified(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: a refund was requested, but there's no evidence yet that
    it was actually issued. Must not be presented as 'refunded'."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([799, 1999]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="SUCCESS",
        source_system="payment_gateway",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="support_system", event_type="REFUND_REQUESTED",
                    event_time=_ts(60), ingested_at=_ts(60.1), source_status="REQUESTED",
                    normalized_status="REFUND_REQUESTED"),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="SUPPORT_RECORD", source_system="support_system",
                        title="Refund request logged", content="Customer requested refund via support ticket.",
                        ingested_at=_ts(60.1), verification_status=VerificationStatus.UNVERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(60), updated_at=_ts(60),
        title=f"Refund requested for {merchant} order #{idx}",
        complaint="Requested a refund, not sure if it was processed.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.AWAITING_EVIDENCE,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="REFUND_REQUESTED_UNVERIFIED",
        expected_reconciliation_status=ReconciliationStatus.REVERSAL_UNVERIFIED,
        expected_safe_next_action="Query refund/reversal status before telling customer it's complete.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, None, events, evidence, [], gt)


def _build_reversal_missing_or_pending(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: payment failed, but there's no reversal record at all —
    distinct from the refund-requested case (no request has even been logged)."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([349, 899]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="FAILED",
        source_system="payment_gateway",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_FAILED",
                    event_time=_ts(0), ingested_at=_ts(0.1), source_status="FAILED",
                    normalized_status="FAILED", amount=amount,
                    verification_status=VerificationStatus.VERIFIED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Payment failed, debit still held",
                        content="Issuer declined; amount shown as debited pending auto-reversal.",
                        ingested_at=_ts(0.1), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(1), updated_at=_ts(1),
        title=f"No reversal seen for failed {merchant} payment #{idx}",
        complaint="Payment failed but amount still shows debited.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.AWAITING_EVIDENCE,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="REVERSAL_MISSING_OR_PENDING",
        expected_reconciliation_status=ReconciliationStatus.REVERSAL_UNVERIFIED,
        expected_safe_next_action="Advise standard reversal SLA window; do not claim refund completed.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, None, events, evidence, [], gt)


def _build_order_expired_or_cancelled(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """Contradiction: payment succeeded after the merchant had already expired
    or cancelled the order (race condition), so the two sides disagree on
    whether the order is still valid."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([599, 1799]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    order_id = ids.next("ORD")
    incident_id = ids.next("INC")
    status = rng.choice([OrderStatus.EXPIRED, OrderStatus.CANCELLED])

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, merchant_order_ref=order_id,
        amount=amount, payment_method="UPI", created_at=_ts(10),
        provider_status="SUCCESS", source_system="payment_gateway",
    )
    order = MerchantOrder(
        order_id=order_id, merchant_id=merchant, payment_attempt_id=pa_id,
        transaction_ref=txn_ref, amount=amount, order_status=status,
        created_at=_ts(0), updated_at=_ts(9), source_system=f"{merchant}_portal",
    )
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="MERCHANT_ORDER", source_system=f"{merchant}_portal",
                        title=f"Order {status.value.lower()} before payment settled",
                        content=f"Order marked {status.value} at T+9min; payment settled at T+10min.",
                        ingested_at=_ts(10.1), verification_status=VerificationStatus.VERIFIED),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(11), updated_at=_ts(11),
        title=f"Paid after {merchant} order {status.value.lower()} #{idx}",
        complaint="Payment went through but order shows expired/cancelled.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.INVESTIGATING,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="ORDER_EXPIRED_OR_CANCELLED",
        expected_reconciliation_status=ReconciliationStatus.STATUS_MISMATCH,
        expected_safe_next_action="Route to merchant for manual reinstatement or refund; do not assume either.",
        is_resolvable=True,
    )
    return Bundle(incident, pa, order, [], evidence, [], gt)


def _build_insufficient_evidence(ids: IdFactory, rng: random.Random, idx: int) -> Bundle:
    """By design, genuinely unresolvable: sources conflict AND a chunk of the
    event log is missing. The correct behavior is to abstain, not guess."""
    merchant = rng.choice(MERCHANTS)
    amount = Decimal(rng.choice([2999, 499]))
    txn_ref = ids.next("TXN")
    pa_id = ids.next("PA")
    incident_id = ids.next("INC")

    pa = PaymentAttempt(
        payment_attempt_id=pa_id, transaction_ref=txn_ref, amount=amount,
        payment_method="UPI", created_at=_ts(0), provider_status="UNKNOWN",
        source_system="payment_gateway",
    )
    events = [
        SourceEvent(event_id=ids.next("EVT"), incident_id=incident_id, transaction_ref=txn_ref,
                    source_system="payment_gateway", event_type="PAYMENT_STATUS",
                    event_time=_ts(0), ingested_at=_ts(45), source_status="UNKNOWN",
                    normalized_status="UNRESOLVED",
                    verification_status=VerificationStatus.CONFLICTED),
    ]
    evidence = [
        EvidenceRecord(evidence_id=ids.next("EVD"), incident_id=incident_id,
                        evidence_type="PROVIDER_RESPONSE", source_system="payment_gateway",
                        title="Gap in event log", content="45-minute gap between request and next known event.",
                        ingested_at=_ts(45), verification_status=VerificationStatus.CONFLICTED,
                        metadata={"gap_minutes": 45}),
    ]
    incident = Incident(
        incident_id=incident_id, created_at=_ts(46), updated_at=_ts(46),
        title=f"Unclear outcome for {merchant} payment #{idx}",
        complaint="Not sure what happened to my payment.",
        transaction_ref=txn_ref, amount=amount, merchant_id=merchant,
        payment_attempt_id=pa_id, incident_status=IncidentStatus.AWAITING_EVIDENCE,
        evidence_ids=[e.evidence_id for e in evidence],
    )
    gt = EvaluationGroundTruth(
        incident_id=incident_id, scenario_category="INSUFFICIENT_EVIDENCE",
        expected_reconciliation_status=ReconciliationStatus.INSUFFICIENT_EVIDENCE,
        expected_safe_next_action="Abstain from a definitive diagnosis; request additional evidence.",
        is_resolvable=False,
        notes="Deliberately unresolvable: correct system behavior is to say so, not to guess.",
    )
    return Bundle(incident, pa, None, events, evidence, [], gt)


SCENARIO_BUILDERS = [
    _build_both_confirmed,
    _build_debit_no_merchant_confirm,
    _build_both_pending,
    _build_missing_notification,
    _build_notification_delivered_not_processed,
    _build_provider_bank_conflict,
    _build_duplicate_notification,
    _build_duplicate_payment_attempt,
    _build_refund_requested_unverified,
    _build_reversal_missing_or_pending,
    _build_order_expired_or_cancelled,
    _build_insufficient_evidence,
]

INCIDENTS_PER_CATEGORY = 834  # 12 categories * 834 = 10008 total (~10k for RAG corpus)


def _build_runbooks(ids: IdFactory) -> list[Runbook]:
    topics = [
        ("Merchant confirmation missing", ["DEBIT_NO_MERCHANT_CONFIRM", "MISSING_NOTIFICATION"]),
        ("Status mismatch between gateway and bank", ["PROVIDER_BANK_CONFLICT", "ORDER_EXPIRED_OR_CANCELLED"]),
        ("Possible duplicate charge", ["DUPLICATE_NOTIFICATION", "DUPLICATE_PAYMENT_ATTEMPT"]),
        ("Refund and reversal not yet verified", ["REFUND_REQUESTED_UNVERIFIED", "REVERSAL_MISSING_OR_PENDING"]),
        ("Handling genuinely insufficient evidence", ["INSUFFICIENT_EVIDENCE", "BOTH_PENDING"]),
    ]
    runbooks = []
    for title, tags in topics:
        runbooks.append(Runbook(
            runbook_id=ids.next("RB"), title=title, scenario_tags=tags,
            content=f"Demo runbook: steps for '{title.lower()}'. SYNTHETIC — not official policy.",
            sections=["Checklist", "Safe actions", "Escalation criteria"],
        ))
    return runbooks


def generate(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    ids = IdFactory()
    bundles: list[Bundle] = []

    global_idx = 0
    for category_idx, builder in enumerate(SCENARIO_BUILDERS):
        for i in range(INCIDENTS_PER_CATEGORY):
            _anchor_minutes[0] = global_idx * TIME_SPREAD_MINUTES
            bundles.append(builder(ids, rng, i + 1))
            global_idx += 1

    incidents = [b.incident for b in bundles]
    payment_attempts = [b.payment_attempt for b in bundles if b.payment_attempt]
    merchant_orders = [b.merchant_order for b in bundles if b.merchant_order]
    events = [e for b in bundles for e in b.events]
    evidence = [e for b in bundles for e in b.evidence]
    notifications = [n for b in bundles for n in b.notifications]
    ground_truths = [b.ground_truth for b in bundles if b.ground_truth]
    runbooks = _build_runbooks(ids)

    return {
        "incidents": incidents,
        "payment_attempts": payment_attempts,
        "merchant_orders": merchant_orders,
        "source_events": events,
        "evidence_records": evidence,
        "notification_records": notifications,
        "runbooks": runbooks,
        "ground_truth": ground_truths,
    }


def _write_json(path: Path, models: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(m.model_dump_json()) for m in models]
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_all(data: dict[str, Any]) -> None:
    _write_json(SYNTHETIC_DIR / "incidents.json", data["incidents"])
    _write_json(SYNTHETIC_DIR / "payment_attempts.json", data["payment_attempts"])
    _write_json(SYNTHETIC_DIR / "merchant_orders.json", data["merchant_orders"])
    _write_json(SYNTHETIC_DIR / "source_events.json", data["source_events"])
    _write_json(SYNTHETIC_DIR / "evidence_records.json", data["evidence_records"])
    _write_json(SYNTHETIC_DIR / "notification_records.json", data["notification_records"])
    _write_json(SYNTHETIC_DIR / "runbooks.json", data["runbooks"])
    # Ground truth deliberately goes to a separate directory from everything else.
    _write_json(EVALUATION_DIR / "ground_truth.json", data["ground_truth"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data = generate(seed=args.seed)
    write_all(data)
    print(f"Generated {len(data['incidents'])} incidents (seed={args.seed}) -> {SYNTHETIC_DIR}")
    print(f"Ground truth -> {EVALUATION_DIR / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
