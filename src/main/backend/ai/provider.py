"""AI provider interface. Both the fake (test) and real (Vertex Gemini)
providers implement this so the orchestrator never knows which one it's
talking to."""
from __future__ import annotations

from typing import Any, Protocol

from src.main.backend.investigation.schemas import InvestigationContext


class InvestigationAIProvider(Protocol):
    model_identifier: str
    source_mode: str  # "SIMULATED" (fake) or "LIVE" (real Vertex call)

    def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
        """Returns a raw dict matching InvestigationReport's fields (minus the
        provenance fields, which the orchestrator fills in itself). Must
        raise AIProviderUnavailable rather than return a fabricated/garbage
        response if it cannot genuinely produce one."""
        ...
