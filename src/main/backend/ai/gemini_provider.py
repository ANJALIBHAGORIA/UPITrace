"""Free-tier Gemini provider via Google AI Studio (generativelanguage API),
NOT Vertex AI — no GCP project/billing needed, just a free API key from
https://aistudio.google.com/apikey. Uses httpx directly (already a
dependency) instead of pulling in a new SDK.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from src.main.backend.investigation.schemas import InvestigationContext

from .exceptions import AIProviderUnavailable

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_REQUIRED_FIELDS = (
    "summary", "confirmed_facts", "competing_hypotheses", "supporting_evidence",
    "contradicting_evidence", "missing_evidence", "recommended_checks",
    "recommended_next_action", "reasoning", "uncertainty_explanation",
    "citation_ids", "unresolved_status",
)


class GeminiFreeProvider:
    source_mode = "LIVE"

    def __init__(self, model_identifier: str | None = None) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_identifier = model_identifier or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        if not self.api_key:
            raise AIProviderUnavailable("GEMINI_API_KEY is not set.")

    def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
        prompt = (
            context.to_prompt_text()
            + "\n\nRespond with ONLY a JSON object with exactly these keys: "
            + ", ".join(_REQUIRED_FIELDS)
            + ". citation_ids must only contain IDs listed above as available evidence or runbooks."
        )
        url = _ENDPOINT.format(model=self.model_identifier)
        try:
            resp = httpx.post(
                url, params={"key": self.api_key}, timeout=30.0,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            raise AIProviderUnavailable(f"Gemini API call failed: {exc}") from exc

        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AIProviderUnavailable(f"Gemini returned non-JSON output: {exc}") from exc

        missing = [f for f in _REQUIRED_FIELDS if f not in parsed]
        if missing:
            raise AIProviderUnavailable(f"Gemini output missing fields: {missing}")
        return parsed
