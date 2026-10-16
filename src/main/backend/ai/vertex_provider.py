"""Real Vertex AI Gemini provider (spec section 8).

Requires `google-cloud-aiplatform`, a configured `GOOGLE_CLOUD_PROJECT` /
`VERTEX_AI_LOCATION`, and valid Application Default Credentials. On this
development machine none of those are present, so this code path is correct
but unexercised — confirmed by `test_vertex_provider_unavailable_without_credentials`.
It must never be used to fabricate a response: any failure to initialize or
call the model raises `AIProviderUnavailable` instead of returning a guess.
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
        self.model_identifier = model_identifier or os.environ.get(
            "VERTEX_AI_GEMINI_MODEL", ""
        )
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self._location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        if not self._project:
            raise AIProviderUnavailable("GOOGLE_CLOUD_PROJECT is not set.")
        if not self.model_identifier:
            raise AIProviderUnavailable("VERTEX_AI_GEMINI_MODEL is not set.")

        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError as exc:
            raise AIProviderUnavailable(f"google-cloud-aiplatform not installed: {exc}") from exc

        try:
            vertexai.init(project=self._project, location=self._location)
            self._model = GenerativeModel(self.model_identifier)
        except Exception as exc:  # auth failures, bad project, etc. — never fabricate instead
            raise AIProviderUnavailable(f"Vertex AI initialization failed: {exc}") from exc

    def generate_investigation(self, context: InvestigationContext) -> dict[str, Any]:
        prompt = (
            context.to_prompt_text()
            + "\n\nRespond with a single JSON object with exactly these keys: "
            + ", ".join(_RESPONSE_SCHEMA_FIELDS)
            + ". citation_ids must only contain IDs listed above as available evidence or runbooks."
        )
        try:
            response = self._model.generate_content(prompt)
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
