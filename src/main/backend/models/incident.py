"""Incident domain model (spec section 3.1)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from .enums import IncidentStatus, ReconciliationStatus, SourceMode


class Incident(BaseModel):
    incident_id: str
    created_at: datetime
    updated_at: datetime
    title: str
    complaint: str
    transaction_ref: Optional[str] = None
    amount: Decimal
    currency: str = "INR"
    merchant_id: str
    payment_attempt_id: Optional[str] = None
    incident_status: IncidentStatus = IncidentStatus.OPEN
    reconciliation_status: Optional[ReconciliationStatus] = None
    source_mode: SourceMode = SourceMode.SIMULATED
    evidence_ids: list[str] = Field(default_factory=list)

    # Evaluation-only reference. Must never be read by the (future) investigation
    # pipeline — the ground-truth record it points to lives in a separate model
    # (EvaluationGroundTruth) and a separate data directory (data/evaluation/).
    ground_truth_id: Optional[str] = None
