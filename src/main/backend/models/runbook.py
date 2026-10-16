"""Runbook domain model (spec section 3.7)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Runbook(BaseModel):
    runbook_id: str
    title: str
    scenario_tags: list[str] = Field(default_factory=list)
    content: str
    sections: list[str] = Field(default_factory=list)

    # Synthetic runbooks are demo procedures only — never official bank/RBI policy.
    source: str = "SYNTHETIC_DEMO"
    version: str = "1.0"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
