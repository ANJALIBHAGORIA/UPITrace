"""Evaluation-only ground truth. Lives in a separate module and separate data
directory (data/evaluation/) from production records (data/synthetic/) so the
investigation pipeline has no import path to it.
"""
from pydantic import BaseModel

from .enums import ReconciliationStatus


class EvaluationGroundTruth(BaseModel):
    incident_id: str
    scenario_category: str
    expected_reconciliation_status: ReconciliationStatus
    expected_safe_next_action: str
    is_resolvable: bool  # False for "insufficient evidence" scenarios by design
    notes: str = ""
