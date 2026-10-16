"""Finding/Citation model (spec section 3.8)."""
from pydantic import BaseModel, Field

from .enums import FindingType


class Finding(BaseModel):
    finding_id: str
    claim: str
    finding_type: FindingType

    # Every finding must point at real evidence. Phase 3's verification step is
    # responsible for rejecting any finding whose evidence_ids don't resolve to
    # an actual EvidenceRecord — the model just makes the field non-optional
    # and non-empty-by-convention (checked in tests, not enforced by Pydantic
    # alone since that needs the evidence store).
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    confidence_label: str
    verified_by_backend: bool = False
