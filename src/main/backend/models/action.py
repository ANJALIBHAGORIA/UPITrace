"""ActionProposal and ActionExecution models (spec section 3.9)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import ActionStatus, ExecutionMode, ExecutionStatus


class ActionProposal(BaseModel):
    action_id: str
    incident_id: str
    action_type: str
    description: str
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    policy_check_status: str = "PENDING"
    requires_human_approval: bool = True
    proposed_at: datetime
    status: ActionStatus = ActionStatus.PROPOSED


class ActionExecution(BaseModel):
    execution_id: str
    action_id: str
    idempotency_key: str

    # SIMULATED is the only mode allowed in Phases 1-4. LIVE is a distinct value
    # the executor must opt into explicitly and is out of scope here.
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    executed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    audit_record_id: Optional[str] = None
