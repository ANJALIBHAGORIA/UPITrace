"""Phase 1 acceptance tests: domain model validity."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.main.backend.models import (
    ActionExecution,
    ActionProposal,
    AuditRecord,
    EvaluationGroundTruth,
    EvidenceRecord,
    ExecutionMode,
    FindingType,
    Incident,
    IncidentStatus,
    MerchantOrder,
    NotificationRecord,
    OrderStatus,
    PaymentAttempt,
    ReconciliationStatus,
    Runbook,
    SourceEvent,
    VerificationStatus,
)
from src.main.backend.models.investigation import Finding

NOW = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)


def test_incident_valid():
    inc = Incident(
        incident_id="INC-0001", created_at=NOW, updated_at=NOW, title="t",
        complaint="c", amount="499.00", merchant_id="IRCTC",
    )
    assert inc.incident_status == IncidentStatus.OPEN
    assert inc.currency == "INR"


def test_incident_rejects_bad_status():
    with pytest.raises(ValidationError):
        Incident(
            incident_id="INC-0002", created_at=NOW, updated_at=NOW, title="t",
            complaint="c", amount="100", merchant_id="IRCTC",
            incident_status="NOT_A_REAL_STATUS",
        )


def test_merchant_order_not_found_is_explicit_state():
    order = MerchantOrder(
        order_id="ORD-0001", merchant_id="IRCTC", amount="100",
        order_status=OrderStatus.NOT_FOUND, created_at=NOW, updated_at=NOW,
        source_system="IRCTC_portal",
    )
    assert order.order_status == OrderStatus.NOT_FOUND


def test_source_event_keeps_event_time_and_ingested_at_distinct():
    ingested = datetime(2026, 10, 12, 10, 5, 0, tzinfo=timezone.utc)
    evt = SourceEvent(
        event_id="EVT-0001", incident_id="INC-0001", source_system="payment_gateway",
        event_type="PAYMENT_SUCCESS", event_time=NOW, ingested_at=ingested,
        source_status="SUCCESS", normalized_status="CONFIRMED",
    )
    assert evt.event_time != evt.ingested_at
    assert evt.verification_status == VerificationStatus.UNVERIFIED  # safe default


def test_evidence_record_requires_core_fields():
    with pytest.raises(ValidationError):
        EvidenceRecord(incident_id="INC-0001")  # missing required fields


def test_notification_delivery_and_processing_are_independent():
    from src.main.backend.models import DeliveryStatus, ProcessingStatus

    notif = NotificationRecord(
        notification_id="NOTIF-0001", destination_system="IRCTC_webhook",
        delivery_status=DeliveryStatus.DELIVERED,
        processing_status=ProcessingStatus.NOT_PROCESSED,
        created_at=NOW,
    )
    assert notif.delivery_status == DeliveryStatus.DELIVERED
    assert notif.processing_status == ProcessingStatus.NOT_PROCESSED


def test_finding_requires_finding_type_enum():
    f = Finding(
        finding_id="F-0001", claim="Payment settled", finding_type=FindingType.FACT,
        evidence_ids=["EVD-0001"], explanation="Gateway confirmed settlement.",
        confidence_label="high",
    )
    assert f.verified_by_backend is False  # unverified until backend checks it


def test_action_execution_defaults_to_simulated():
    exc = ActionExecution(execution_id="X-0001", action_id="A-0001", idempotency_key="k1")
    assert exc.execution_mode == ExecutionMode.SIMULATED


def test_action_proposal_requires_human_approval_by_default():
    prop = ActionProposal(
        action_id="A-0001", incident_id="INC-0001", action_type="RETRY_NOTIFY",
        description="Retry webhook", rationale="Delivery failed earlier.",
        proposed_at=NOW,
    )
    assert prop.requires_human_approval is True


def test_audit_record_rejects_secret_like_metadata_keys():
    with pytest.raises(ValidationError):
        AuditRecord(
            audit_record_id="AUD-0001", incident_id="INC-0001", actor_id="system",
            event_type="ACTION_EXECUTED", timestamp=NOW, result="ok",
            metadata={"customer_otp": "123456"},
        )


def test_audit_record_accepts_clean_metadata():
    rec = AuditRecord(
        audit_record_id="AUD-0002", incident_id="INC-0001", actor_id="system",
        event_type="ACTION_EXECUTED", timestamp=NOW, result="ok",
        metadata={"action_type": "RETRY_NOTIFY"},
    )
    assert rec.metadata["action_type"] == "RETRY_NOTIFY"


def test_runbook_defaults_to_synthetic_source():
    rb = Runbook(runbook_id="RB-0001", title="t", content="c")
    assert rb.source == "SYNTHETIC_DEMO"


def test_evaluation_ground_truth_is_a_separate_model():
    gt = EvaluationGroundTruth(
        incident_id="INC-0001", scenario_category="BOTH_PENDING",
        expected_reconciliation_status=ReconciliationStatus.PENDING,
        expected_safe_next_action="Wait.", is_resolvable=True,
    )
    assert gt.expected_reconciliation_status == ReconciliationStatus.PENDING
