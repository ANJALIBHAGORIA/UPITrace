"""Request/response schemas specific to API routes (not already covered by
domain or tool schemas)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CreateIncidentRequest(BaseModel):
    title: str
    complaint: str
    transaction_ref: Optional[str] = None
    amount: Decimal
    currency: str = "INR"
    merchant_id: str
    payment_attempt_id: Optional[str] = None


class ProposeActionRequest(BaseModel):
    actor_id: str = "system"


class ExecuteActionRequest(BaseModel):
    actor_id: str
    idempotency_key: str


class VerifyActionRequest(BaseModel):
    expected_result: str


class SampleIncidentSummary(BaseModel):
    incident_id: str
    title: str
    scenario_category: str


class SimilarCase(BaseModel):
    incident_id: str
    title: str
    similarity_score: float
    shared_terms: list[str]
