"""In-memory repository for Phase 2.

Stands in for Firestore (Phase 5). Holds everything produced by the Phase 1
synthetic data generator plus whatever the API creates at runtime (new
incidents, action proposals/executions, audit records). Ground truth is kept
in a separate attribute, loaded only by tests/evaluation code — no API route
in this module ever reads or returns it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.main.backend.models import (
    ActionExecution,
    ActionProposal,
    AuditRecord,
    EvaluationGroundTruth,
    EvidenceRecord,
    Incident,
    MerchantOrder,
    NotificationRecord,
    PaymentAttempt,
    Runbook,
    SourceEvent,
)

DEFAULT_SYNTHETIC_DIR = Path(__file__).resolve().parent / "data" / "synthetic"
DEFAULT_EVALUATION_DIR = Path(__file__).resolve().parent / "data" / "evaluation"


class InMemoryStore:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.payment_attempts: dict[str, PaymentAttempt] = {}
        self.merchant_orders: dict[str, MerchantOrder] = {}
        self.source_events: dict[str, SourceEvent] = {}
        self.evidence_records: dict[str, EvidenceRecord] = {}
        self.notification_records: dict[str, NotificationRecord] = {}
        self.runbooks: dict[str, Runbook] = {}
        self.action_proposals: dict[str, ActionProposal] = {}
        self.action_executions: dict[str, ActionExecution] = {}
        self.audit_records: list[AuditRecord] = []
        # Evaluation-only. Never serve this through an API route.
        self.ground_truth: dict[str, EvaluationGroundTruth] = {}

    # -- loading -----------------------------------------------------------
    def load_synthetic(self, synthetic_dir: Path = DEFAULT_SYNTHETIC_DIR) -> None:
        def _load(filename: str) -> list[dict]:
            path = synthetic_dir / filename
            return json.loads(path.read_text()) if path.exists() else []

        for raw in _load("incidents.json"):
            inc = Incident(**raw)
            self.incidents[inc.incident_id] = inc
        for raw in _load("payment_attempts.json"):
            pa = PaymentAttempt(**raw)
            self.payment_attempts[pa.payment_attempt_id] = pa
        for raw in _load("merchant_orders.json"):
            order = MerchantOrder(**raw)
            self.merchant_orders[order.order_id] = order
        for raw in _load("source_events.json"):
            evt = SourceEvent(**raw)
            self.source_events[evt.event_id] = evt
        for raw in _load("evidence_records.json"):
            ev = EvidenceRecord(**raw)
            self.evidence_records[ev.evidence_id] = ev
        for raw in _load("notification_records.json"):
            notif = NotificationRecord(**raw)
            self.notification_records[notif.notification_id] = notif
        for raw in _load("runbooks.json"):
            rb = Runbook(**raw)
            self.runbooks[rb.runbook_id] = rb

    def load_ground_truth(self, evaluation_dir: Path = DEFAULT_EVALUATION_DIR) -> None:
        path = evaluation_dir / "ground_truth.json"
        if not path.exists():
            return
        for raw in json.loads(path.read_text()):
            gt = EvaluationGroundTruth(**raw)
            self.ground_truth[gt.incident_id] = gt

    # -- query helpers -------------------------------------------------------
    def events_for_incident(self, incident_id: str) -> list[SourceEvent]:
        return [e for e in self.source_events.values() if e.incident_id == incident_id]

    def evidence_for_incident(self, incident_id: str) -> list[EvidenceRecord]:
        return [e for e in self.evidence_records.values() if e.incident_id == incident_id]

    def notifications_for_payment_attempt(self, payment_attempt_id: str) -> list[NotificationRecord]:
        return [n for n in self.notification_records.values() if n.payment_attempt_id == payment_attempt_id]

    def merchant_order_for(
        self, payment_attempt_id: Optional[str] = None, transaction_ref: Optional[str] = None
    ) -> Optional[MerchantOrder]:
        for order in self.merchant_orders.values():
            if payment_attempt_id and order.payment_attempt_id == payment_attempt_id:
                return order
            if transaction_ref and order.transaction_ref == transaction_ref:
                return order
        return None

    def runbooks_matching(self, tags: list[str], query: str = "") -> list[Runbook]:
        matches = [rb for rb in self.runbooks.values() if any(t in rb.scenario_tags for t in tags)]
        if query:
            q = query.lower()
            matches = [rb for rb in matches if q in rb.title.lower() or q in rb.content.lower()] or matches
        return matches


def load_default_store() -> InMemoryStore:
    store = InMemoryStore()
    store.load_synthetic()
    store.load_ground_truth()
    return store
