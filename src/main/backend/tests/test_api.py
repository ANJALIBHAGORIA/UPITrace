"""Phase 2 acceptance tests: FastAPI routes (spec section 7), via TestClient
against the real synthetic dataset — no mocked HTTP layer."""
from fastapi.testclient import TestClient

from src.main.backend.api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["incidents_loaded"] >= 30


def test_list_incidents_returns_synthetic_data():
    r = client.get("/api/v1/incidents")
    assert r.status_code == 200
    assert len(r.json()) >= 30


def test_get_unknown_incident_is_404():
    r = client.get("/api/v1/incidents/INC-DOES-NOT-EXIST")
    assert r.status_code == 404


def test_create_incident_then_fetch_it():
    payload = {
        "title": "Test incident", "complaint": "c", "amount": "100.00",
        "merchant_id": "IRCTC",
    }
    created = client.post("/api/v1/incidents", json=payload)
    assert created.status_code == 201
    incident_id = created.json()["incident_id"]

    fetched = client.get(f"/api/v1/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Test incident"
    assert fetched.json()["incident_status"] == "OPEN"


def test_reconcile_known_both_confirmed_incident():
    incidents = client.get("/api/v1/incidents").json()
    target = next(i for i in incidents if "Payment to" in i["title"] and "#1" in i["title"])
    r = client.post(f"/api/v1/incidents/{target['incident_id']}/reconcile")
    assert r.status_code == 200
    body = r.json()
    assert body["classification"] == "CONFIRMED"
    assert body["incident_id"] == target["incident_id"]


def test_investigate_falls_back_honestly_without_vertex_credentials():
    """No Google Cloud credentials are configured on this machine, so this
    must come back as an explicit UNAVAILABLE fallback, not a fabricated
    Gemini-shaped answer and not a generic 500."""
    incidents = client.get("/api/v1/incidents").json()
    incident_id = incidents[0]["incident_id"]
    r = client.post(f"/api/v1/incidents/{incident_id}/investigate")
    assert r.status_code == 200
    body = r.json()
    assert body["ai_used"] is False
    assert body["source_mode"] == "UNAVAILABLE"
    assert body["model_identifier"] == "none (deterministic fallback)"


def test_get_investigation_before_running_is_404():
    # A freshly created incident is guaranteed never to have been investigated,
    # regardless of what other tests in this module have already done.
    created = client.post("/api/v1/incidents", json={
        "title": "fresh", "complaint": "c", "amount": "50", "merchant_id": "IRCTC",
    })
    incident_id = created.json()["incident_id"]
    r = client.get(f"/api/v1/incidents/{incident_id}/investigation")
    assert r.status_code == 404


def test_investigate_then_get_investigation_returns_same_report():
    created = client.post("/api/v1/incidents", json={
        "title": "fresh2", "complaint": "c", "amount": "50", "merchant_id": "IRCTC",
    })
    incident_id = created.json()["incident_id"]
    posted = client.post(f"/api/v1/incidents/{incident_id}/investigate")
    fetched = client.get(f"/api/v1/incidents/{incident_id}/investigation")
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == posted.json()["summary"]


def test_get_events_and_evidence_for_incident():
    incidents = client.get("/api/v1/incidents").json()
    incident_id = incidents[0]["incident_id"]
    events = client.get(f"/api/v1/incidents/{incident_id}/events")
    evidence = client.get(f"/api/v1/incidents/{incident_id}/evidence")
    assert events.status_code == 200
    assert evidence.status_code == 200


def test_similar_cases_returns_real_computed_scores():
    incidents = client.get("/api/v1/incidents").json()
    incident_id = incidents[0]["incident_id"]
    r = client.get(f"/api/v1/incidents/{incident_id}/similar-cases")
    assert r.status_code == 200
    for case in r.json():
        assert 0.0 < case["similarity_score"] <= 1.0
        assert case["incident_id"] != incident_id


def test_list_runbooks_and_filter_by_tag():
    all_rb = client.get("/api/v1/runbooks").json()
    assert len(all_rb) > 0
    filtered = client.get("/api/v1/runbooks", params={"tag": "INSUFFICIENT_EVIDENCE"}).json()
    assert all("INSUFFICIENT_EVIDENCE" in rb["scenario_tags"] for rb in filtered)


def test_sample_incidents_do_not_leak_expected_outcome():
    r = client.get("/api/v1/sample-incidents")
    assert r.status_code == 200
    samples = r.json()
    assert len(samples) == 12  # one per scenario category
    for sample in samples:
        assert set(sample.keys()) == {"incident_id", "title", "scenario_category"}
        assert "expected_reconciliation_status" not in sample
        assert "expected_safe_next_action" not in sample


def test_full_action_lifecycle_propose_execute_verify():
    incidents = client.get("/api/v1/incidents").json()
    incident_id = incidents[1]["incident_id"]

    proposal = client.post(f"/api/v1/incidents/{incident_id}/actions/propose", json={"actor_id": "tester"})
    assert proposal.status_code == 200
    action_id = proposal.json()["action_id"]
    action_type = proposal.json()["action_type"]

    execution = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={"actor_id": "tester", "idempotency_key": f"idem-{action_id}"},
    )
    assert execution.status_code == 200
    assert execution.json()["approved"] is True

    verification = client.post(
        f"/api/v1/actions/{action_id}/verify", json={"expected_result": action_type},
    )
    assert verification.status_code == 200
    assert verification.json()["result"] == "VERIFIED"

    audit_trail = client.get(f"/api/v1/incidents/{incident_id}/audit").json()
    event_types = {a["event_type"] for a in audit_trail}
    assert "ACTION_PROPOSED" in event_types
    assert "ACTION_EXECUTION_REQUESTED" in event_types
    assert "OUTCOME_VERIFIED" in event_types


def test_verify_before_execute_is_rejected_not_fabricated():
    incidents = client.get("/api/v1/incidents").json()
    incident_id = incidents[2]["incident_id"]
    proposal = client.post(f"/api/v1/incidents/{incident_id}/actions/propose", json={"actor_id": "tester"})
    action_id = proposal.json()["action_id"]

    r = client.post(f"/api/v1/actions/{action_id}/verify", json={"expected_result": "anything"})
    assert r.status_code == 409
