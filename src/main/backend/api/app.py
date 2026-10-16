"""FastAPI app (spec section 7). Routes are thin wrappers around store +
reconciliation engine + tools + investigation orchestrator — no business
logic lives here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from src.main.backend import audit
from src.main.backend.investigation.orchestrator import run_investigation
from src.main.backend.investigation.schemas import InvestigationReport
from src.main.backend.models import Incident, IncidentStatus
from src.main.backend.reconciliation import apply_reconciliation
from src.main.backend.store import InMemoryStore, load_default_store
from src.main.backend.tools import schemas as tool_schemas
from src.main.backend.tools import service as tools

from . import schemas as api_schemas

app = FastAPI(title="UPITrace API", version="0.1.0-phase3")

store: InMemoryStore = load_default_store()
_incident_counter = count(len(store.incidents) + 1)
# Kept here rather than on InMemoryStore to avoid a store -> investigation ->
# reconciliation -> store import cycle.
_investigation_reports: dict[str, InvestigationReport] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "incidents_loaded": len(store.incidents)}


@app.get("/api/v1/incidents")
def list_incidents(status: Optional[str] = Query(default=None)) -> list[Incident]:
    incidents = list(store.incidents.values())
    if status:
        incidents = [i for i in incidents if i.incident_status.value == status]
    return incidents


@app.post("/api/v1/incidents", status_code=201)
def create_incident(req: api_schemas.CreateIncidentRequest) -> Incident:
    incident_id = f"INC-{next(_incident_counter):04d}"
    now = datetime.now(timezone.utc)
    incident = Incident(
        incident_id=incident_id, created_at=now, updated_at=now,
        title=req.title, complaint=req.complaint, transaction_ref=req.transaction_ref,
        amount=req.amount, currency=req.currency, merchant_id=req.merchant_id,
        payment_attempt_id=req.payment_attempt_id, incident_status=IncidentStatus.OPEN,
    )
    store.incidents[incident_id] = incident
    audit.record(store, incident_id=incident_id, actor_id="api_client",
                 event_type="INCIDENT_CREATED", result="ok")
    return incident


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: str) -> Incident:
    incident = store.incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    return incident


@app.get("/api/v1/incidents/{incident_id}/events")
def get_incident_events(incident_id: str) -> list:
    _require_incident(incident_id)
    return store.events_for_incident(incident_id)


@app.get("/api/v1/incidents/{incident_id}/evidence")
def get_incident_evidence(incident_id: str) -> list:
    _require_incident(incident_id)
    return store.evidence_for_incident(incident_id)


@app.post("/api/v1/incidents/{incident_id}/reconcile")
def reconcile_incident(incident_id: str):
    _require_incident(incident_id)
    result = apply_reconciliation(store, incident_id)
    audit.record(
        store, incident_id=incident_id, actor_id="reconciliation_engine",
        event_type="RECONCILIATION_RUN", result=result.classification.value,
        metadata={"rules_applied": result.rules_applied},
    )
    return result


@app.post("/api/v1/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: str) -> InvestigationReport:
    _require_incident(incident_id)
    report = run_investigation(store, incident_id)
    _investigation_reports[incident_id] = report
    return report


@app.get("/api/v1/incidents/{incident_id}/investigation")
def get_investigation(incident_id: str) -> InvestigationReport:
    _require_incident(incident_id)
    report = _investigation_reports.get(incident_id)
    if report is None:
        raise HTTPException(404, f"incident {incident_id} has not been investigated yet; POST /investigate first")
    return report


@app.get("/api/v1/incidents/{incident_id}/similar-cases")
def similar_cases(incident_id: str, limit: int = 3) -> list[api_schemas.SimilarCase]:
    """Lexical (word-overlap) similarity over title+complaint. Real, computed
    scores — not placeholders — but not the hybrid lexical+semantic retrieval
    promised for Phase 3 (no embeddings yet)."""
    target = _require_incident(incident_id)
    target_terms = _tokenize(target.title + " " + target.complaint)

    scored = []
    for other in store.incidents.values():
        if other.incident_id == incident_id:
            continue
        other_terms = _tokenize(other.title + " " + other.complaint)
        shared = target_terms & other_terms
        union = target_terms | other_terms
        score = len(shared) / len(union) if union else 0.0
        if score > 0:
            scored.append(api_schemas.SimilarCase(
                incident_id=other.incident_id, title=other.title,
                similarity_score=round(score, 3), shared_terms=sorted(shared),
            ))
    scored.sort(key=lambda c: c.similarity_score, reverse=True)
    return scored[:limit]


@app.get("/api/v1/runbooks")
def list_runbooks(tag: Optional[str] = Query(default=None)) -> list:
    runbooks = list(store.runbooks.values())
    if tag:
        runbooks = [rb for rb in runbooks if tag in rb.scenario_tags]
    return runbooks


@app.get("/api/v1/sample-incidents")
def sample_incidents() -> list[api_schemas.SampleIncidentSummary]:
    """One example per scenario category, for the 'try a sample case' UI
    button. Exposes only incident_id/title/category — never the expected
    reconciliation outcome, which stays in the evaluation-only ground truth."""
    seen_categories: set[str] = set()
    out = []
    for incident in store.incidents.values():
        gt = store.ground_truth.get(incident.incident_id)
        if gt is None or gt.scenario_category in seen_categories:
            continue
        seen_categories.add(gt.scenario_category)
        out.append(api_schemas.SampleIncidentSummary(
            incident_id=incident.incident_id, title=incident.title,
            scenario_category=gt.scenario_category,
        ))
    return out


@app.post("/api/v1/incidents/{incident_id}/actions/propose")
def propose_action(incident_id: str, req: api_schemas.ProposeActionRequest):
    _require_incident(incident_id)
    reconciliation = apply_reconciliation(store, incident_id)  # cheap & deterministic; safe to re-run
    proposal = tools.propose_resolution(store, incident_id, reconciliation)
    audit.record(store, incident_id=incident_id, actor_id=req.actor_id,
                 event_type="ACTION_PROPOSED", result=proposal.action_type,
                 output_reference=proposal.action_id)
    return proposal


@app.post("/api/v1/actions/{action_id}/execute")
def execute_action(action_id: str, req: api_schemas.ExecuteActionRequest):
    if action_id not in store.action_proposals:
        raise HTTPException(404, f"action {action_id} not found")
    result = tools.request_action(
        store, tool_schemas.RequestActionInput(
            action_id=action_id, actor_id=req.actor_id, idempotency_key=req.idempotency_key,
        ),
    )
    proposal = store.action_proposals[action_id]
    audit.record(
        store, incident_id=proposal.incident_id, actor_id=req.actor_id,
        event_type="ACTION_EXECUTION_REQUESTED", result=result.reason,
        output_reference=result.execution_id,
    )
    return result


@app.post("/api/v1/actions/{action_id}/verify")
def verify_action(action_id: str, req: api_schemas.VerifyActionRequest):
    proposal = store.action_proposals.get(action_id)
    if proposal is None:
        raise HTTPException(404, f"action {action_id} not found")
    execution = next(
        (e for e in store.action_executions.values() if e.action_id == action_id), None,
    )
    if execution is None:
        raise HTTPException(409, f"action {action_id} has not been executed yet")
    result = tools.verify_outcome(
        store, tool_schemas.VerifyOutcomeInput(
            execution_id=execution.execution_id, expected_result=req.expected_result,
        ),
    )
    audit.record(store, incident_id=proposal.incident_id, actor_id="api_client",
                 event_type="OUTCOME_VERIFIED", result=result.result.value)
    return result


@app.get("/api/v1/incidents/{incident_id}/audit")
def get_audit(incident_id: str) -> list:
    _require_incident(incident_id)
    return [a for a in store.audit_records if a.incident_id == incident_id]


def _require_incident(incident_id: str) -> Incident:
    incident = store.incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    return incident


def _tokenize(text: str) -> set[str]:
    return {w.strip(".,!?#").lower() for w in text.split() if len(w) > 2}
