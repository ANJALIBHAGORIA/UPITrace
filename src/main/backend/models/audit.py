"""AuditRecord model (spec section 3.10)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .enums import ExecutionMode

_FORBIDDEN_METADATA_KEYS = {"password", "pin", "otp", "secret", "credential", "token"}


class AuditRecord(BaseModel):
    audit_record_id: str
    incident_id: str
    actor_id: str
    event_type: str
    timestamp: datetime
    input_reference: Optional[str] = None
    output_reference: Optional[str] = None
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED
    result: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def no_secrets_in_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key in value:
            lowered = key.lower()
            if any(forbidden in lowered for forbidden in _FORBIDDEN_METADATA_KEYS):
                raise ValueError(
                    f"AuditRecord.metadata must not contain secret-like key '{key}'"
                )
        return value
