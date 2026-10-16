"""Typed input/output schemas for the nine agent tools (spec section 6)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.main.backend.models import (
    ActionProposal,
    EvidenceRecord,
    MerchantOrder,
    NotificationRecord,
    OutcomeVerificationResult,
    PaymentAttempt,
    Runbook,
    SourceMode,
)


class FindPaymentAttemptInput(BaseModel):
    transaction_ref: Optional[str] = None
    payment_attempt_id: Optional[str] = None
    merchant_order_ref: Optional[str] = None


class FindPaymentAttemptOutput(BaseModel):
    candidates: list[PaymentAttempt] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    ambiguous: bool = False
    source_mode: SourceMode = SourceMode.SIMULATED


class FetchPaymentStatusInput(BaseModel):
    payment_attempt_id: str


class FetchPaymentStatusOutput(BaseModel):
    found: bool
    provider_status: Optional[str] = None
    source_timestamp: Optional[str] = None
    source_system: Optional[str] = None
    source_mode: SourceMode = SourceMode.SIMULATED


class FetchMerchantOrderInput(BaseModel):
    merchant_id: str
    order_ref: Optional[str] = None
    transaction_ref: Optional[str] = None


class FetchMerchantOrderOutput(BaseModel):
    found: bool
    order: Optional[MerchantOrder] = None
    source_mode: SourceMode = SourceMode.SIMULATED


class InspectNotificationRecordsInput(BaseModel):
    payment_attempt_id: str


class InspectNotificationRecordsOutput(BaseModel):
    notifications: list[NotificationRecord] = Field(default_factory=list)
    source_mode: SourceMode = SourceMode.SIMULATED


class RetrieveBankEvidenceInput(BaseModel):
    incident_id: str


class RetrieveBankEvidenceOutput(BaseModel):
    records: list[EvidenceRecord] = Field(default_factory=list)
    source_mode: SourceMode = SourceMode.SIMULATED


class RetrieveRunbookInput(BaseModel):
    classification: str
    query: str = ""


class RetrieveRunbookOutput(BaseModel):
    runbooks: list[Runbook] = Field(default_factory=list)
    retrieval_rationale: str = ""


class RequestActionInput(BaseModel):
    action_id: str
    actor_id: str
    idempotency_key: str


class RequestActionOutput(BaseModel):
    approved: bool
    execution_id: Optional[str] = None
    execution_status: Optional[str] = None
    reason: str = ""


class VerifyOutcomeInput(BaseModel):
    execution_id: str
    expected_result: str


class VerifyOutcomeOutput(BaseModel):
    result: OutcomeVerificationResult
    evidence_ids: list[str] = Field(default_factory=list)
