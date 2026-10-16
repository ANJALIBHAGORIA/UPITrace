"""SourceEvent, EvidenceRecord, NotificationRecord models (spec sections 3.4-3.6)."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import DeliveryStatus, ProcessingStatus, SourceMode, VerificationStatus


class SourceEvent(BaseModel):
    event_id: str
    incident_id: str
    transaction_ref: Optional[str] = None
    source_system: str
    event_type: str

    # event_time (when it happened upstream) and ingested_at (when we learned
    # about it) are kept distinct on purpose — never collapse them.
    event_time: datetime
    ingested_at: datetime

    source_status: str
    normalized_status: str
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    correlation_ids: list[str] = Field(default_factory=list)
    raw_record_ref: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_mode: SourceMode = SourceMode.SIMULATED


class EvidenceRecord(BaseModel):
    evidence_id: str
    incident_id: str
    evidence_type: str
    source_system: str
    title: str
    content: str
    raw_record_ref: Optional[str] = None
    event_time: Optional[datetime] = None
    ingested_at: datetime
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_mode: SourceMode = SourceMode.SIMULATED
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationRecord(BaseModel):
    notification_id: str
    event_id: Optional[str] = None
    payment_attempt_id: Optional[str] = None
    destination_system: str

    # Delivery and processing are distinct: a delivered notification does not
    # prove the merchant actually updated its order.
    delivery_status: DeliveryStatus = DeliveryStatus.UNKNOWN
    processing_status: ProcessingStatus = ProcessingStatus.UNKNOWN

    created_at: datetime
    delivered_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    source_mode: SourceMode = SourceMode.SIMULATED
    raw_record_ref: Optional[str] = None
