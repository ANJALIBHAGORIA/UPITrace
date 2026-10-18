"""Safe Vertex AI status check + one minimal real model-call test.

Prints only pass/fail per step and short non-sensitive diagnostic text —
never credentials, never incident data (uses a fixed trivial prompt, not
real incidents). Safe to run and paste output anywhere.

Usage:
    python -m src.main.backend.scripts.check_vertex_status
"""
from __future__ import annotations

import os
import sys


def _check_env() -> bool:
    required = ["GOOGLE_CLOUD_PROJECT", "VERTEX_AI_LOCATION", "VERTEX_AI_GEMINI_MODEL"]
    ok = True
    for var in required:
        value = os.environ.get(var, "")
        status = "set" if value else "MISSING"
        # Print only whether it's set, never the value (project/location aren't
        # secret, but there's no reason to echo them either).
        print(f"  [{'OK' if value else 'FAIL'}] {var}: {status}")
        ok = ok and bool(value)
    return ok


def _check_adc() -> bool:
    try:
        import google.auth
        credentials, project = google.auth.default()
        print(f"  [OK] Application Default Credentials found (detected project: {project or 'none'})")
        return True
    except Exception as exc:
        print(f"  [FAIL] No Application Default Credentials found: {exc}")
        print("         Run: gcloud auth application-default login")
        return False


def _check_real_call() -> bool:
    from src.main.backend.ai.exceptions import AIProviderUnavailable
    from src.main.backend.ai.vertex_provider import VertexGeminiProvider
    from src.main.backend.investigation.schemas import InvestigationContext
    from src.main.backend.models import Incident, IncidentStatus, ReconciliationStatus
    from src.main.backend.reconciliation import ReconciliationResult
    from datetime import datetime, timezone

    # Deliberately fake/trivial data — this call must never send real incident data.
    fake_incident = Incident(
        incident_id="STATUS-CHECK", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), title="status check", complaint="status check",
        amount="1", merchant_id="TEST", incident_status=IncidentStatus.OPEN,
    )
    fake_recon = ReconciliationResult(
        incident_id="STATUS-CHECK", classification=ReconciliationStatus.UNRESOLVED,
    )
    context = InvestigationContext(incident=fake_incident, reconciliation=fake_recon)

    try:
        provider = VertexGeminiProvider()
    except AIProviderUnavailable as exc:
        print(f"  [FAIL] Could not construct VertexGeminiProvider: {exc}")
        return False

    try:
        result = provider.generate_investigation(context)
        print(f"  [OK] Real Vertex AI call succeeded (model: {provider.model_identifier})")
        print(f"       Response summary (truncated): {result['summary'][:80]}...")
        return True
    except AIProviderUnavailable as exc:
        print(f"  [FAIL] Real Vertex AI call failed: {exc}")
        return False


def main() -> None:
    print("1. Environment variables")
    env_ok = _check_env()

    print("\n2. Application Default Credentials")
    adc_ok = _check_adc()

    print("\n3. Real model call (trivial, non-sensitive test data only)")
    if env_ok and adc_ok:
        call_ok = _check_real_call()
    else:
        print("  [SKIPPED] Fix steps 1-2 first.")
        call_ok = False

    print("\n" + "=" * 50)
    if env_ok and adc_ok and call_ok:
        print("RESULT: Vertex AI is configured and a real call succeeded.")
    else:
        print("RESULT: Vertex AI is NOT fully working yet. See failures above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
