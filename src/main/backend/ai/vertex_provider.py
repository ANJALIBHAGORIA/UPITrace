"""Vertex AI Gemini provider — the explicit, selected production provider
(spec section 8, migration from Google AI Studio).

Uses Google's current `google-genai` SDK in Vertex mode
(`genai.Client(vertexai=True, ...)`), NOT the deprecated
`vertexai.generative_models` module. Authenticates via Application Default
Credentials — never reads GEMINI_API_KEY. If ADC, project config, or the
model call fail for any reason, this raises AIProviderUnavailable; the
orchestrator does NOT silently retry against the AI Studio API when that
happens — it falls through to the deterministic (non-AI) result instead,
same as any other provider failure.

Model ID is read from VERTEX_AI_GEMINI_MODEL with NO hardcoded default —
Vertex's supported model IDs are not guaranteed to match Google AI Studio's
(confirmed during this migration: AI Studio deprecated `gemini-2.0-flash` in
favor of `gemini-3.8-flash`; Vertex's own supported/GA model list is
independent and must be verified separately, see
scripts/check_vertex_status.py). Assuming the AI Studio model ID works here
would violate that requirement, so an unset model ID fails closed.
"""
from __future__ import annotations

import json
import os
from typing import Any

from src.main.backend.investigation.schemas import InvestigationContext

from .exceptions import AIProviderUnavailable

_RESPONSE_SCHEMA_FIELDS = (
    "summary", "confirmed_facts", "competing_hypotheses", "supporting_evidence",
    "contradicting_evidence", "missing_evidence", "recommended_checks",
    "recommended_next_action", "reasoning", "uncertainty_explanation",
    "citation_ids", "unresolved_status",
)


class VertexGeminiProvider:
    source_mode = "LIVE"

    def __init__(self, model_identifier: str | None = None) -> None:
        self.model_identifier = model_identifier or os.environ.get("VERTEX_AI_GEMINI_MODEL", "")
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT", "upitrace")
        self._location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        if not self.model_identifier:
            raise AIProviderUnavailable(
                "VERTEX_AI_GEMINI_MODEL is not set. Do not assume an AI-Studio model ID is "
                "valid on Vertex — verify with scripts/check_vertex_status.py first."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise AIProviderUnavailable(f"google-genai not installed: {exc}") from exc

        try:
            self._client = genai.Client(vertexai=True, project=self._project, location=self._location)
        except Exception as exc:  # ADC missing, bad project, etc. — never fabricate instead
            raise AIProviderUnavailable(f"Vertex AI client initialization failed: {exc}") from exc

    def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
        from google.genai import types

        prompt = (
            context.to_prompt_text()
            + "\n\nRespond with a single JSON object with exactly these keys: "
            + ", ".join(_RESPONSE_SCHEMA_FIELDS)
            + ". citation_ids must only contain IDs listed above as available evidence or runbooks."
        )
        try:
            response = self._client.models.generate_content(
                model=self.model_identifier, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            raw_text = response.text
        except Exception as exc:
            raise AIProviderUnavailable(f"Vertex AI call failed: {exc}") from exc

        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AIProviderUnavailable(f"Vertex AI returned non-JSON output: {exc}") from exc

        missing_fields = [f for f in _RESPONSE_SCHEMA_FIELDS if f not in parsed]
        if missing_fields:
            raise AIProviderUnavailable(f"Vertex AI output missing fields: {missing_fields}")
        return parsed
