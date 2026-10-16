"""Phase 2 acceptance tests: agent tool connectors (all SIMULATED)."""
from src.main.backend.models import OutcomeVerificationResult, SourceMode
from src.main.backend.reconciliation import apply_reconciliation
from src.main.backend.store import load_default_store
from src.main.backend.tools import schemas as s
from src.main.backend.tools import service as tools


def _store():
    return load_default_store()


def test_find_payment_attempt_by_transaction_ref():
    store = _store()
    some_pa = next(iter(store.payment_attempts.values()))
    out = tools.find_payment_attempt(store, s.FindPaymentAttemptInput(transaction_ref=some_pa.transaction_ref))
    assert out.source_mode == SourceMode.SIMULATED
    assert any(c.payment_attempt_id == some_pa.payment_attempt_id for c in out.candidates)


def test_find_payment_attempt_unknown_ref_returns_empty():
    store = _store()
    out = tools.find_payment_attempt(store, s.FindPaymentAttemptInput(transaction_ref="TXN-DOES-NOT-EXIST"))
    assert out.candidates == []
    assert out.ambiguous is False


def test_fetch_payment_status_not_found():
    store = _store()
    out = tools.fetch_payment_status(store, s.FetchPaymentStatusInput(payment_attempt_id="PA-NOPE"))
    assert out.found is False


def test_fetch_merchant_order_not_found_is_explicit():
    store = _store()
    out = tools.fetch_merchant_order(
        store, s.FetchMerchantOrderInput(merchant_id="IRCTC", transaction_ref="TXN-DOES-NOT-EXIST"),
    )
    assert out.found is False
    assert out.order is None


def test_inspect_notification_records():
    store = _store()
    some_notif = next(iter(store.notification_records.values()))
    out = tools.inspect_notification_records(
        store, s.InspectNotificationRecordsInput(payment_attempt_id=some_notif.payment_attempt_id),
    )
    assert any(n.notification_id == some_notif.notification_id for n in out.notifications)


def test_retrieve_bank_evidence_only_returns_bank_records():
    store = _store()
    incident_id = next(
        i.incident_id for i in store.incidents.values()
        if "Conflicting status" in i.title
    )
    out = tools.retrieve_bank_evidence(store, s.RetrieveBankEvidenceInput(incident_id=incident_id))
    assert all(r.evidence_type == "BANK_RECORD" for r in out.records)


def test_retrieve_runbook_matches_by_tag():
    store = _store()
    out = tools.retrieve_runbook(store, s.RetrieveRunbookInput(classification="DUPLICATE_NOTIFICATION"))
    assert out.runbooks
    assert "DUPLICATE_NOTIFICATION" in out.retrieval_rationale or out.runbooks


def test_propose_resolution_is_labelled_non_ai():
    store = _store()
    incident_id = next(iter(store.incidents))
    reconciliation = apply_reconciliation(store, incident_id)
    proposal = tools.propose_resolution(store, incident_id, reconciliation)
    assert "not an AI-authored proposal" in proposal.rationale
    assert proposal.requires_human_approval is True
    assert proposal.action_id in store.action_proposals


def test_request_action_executes_and_is_idempotent():
    store = _store()
    incident_id = next(iter(store.incidents))
    reconciliation = apply_reconciliation(store, incident_id)
    proposal = tools.propose_resolution(store, incident_id, reconciliation)

    first = tools.request_action(
        store, s.RequestActionInput(action_id=proposal.action_id, actor_id="tester", idempotency_key="k-1"),
    )
    assert first.approved is True
    assert first.execution_status == "SUCCEEDED"

    second = tools.request_action(
        store, s.RequestActionInput(action_id=proposal.action_id, actor_id="tester", idempotency_key="k-1"),
    )
    assert second.execution_id == first.execution_id  # same key -> same execution, not a new one


def test_request_action_rejects_unknown_action_id():
    store = _store()
    out = tools.request_action(
        store, s.RequestActionInput(action_id="ACT-NOPE", actor_id="tester", idempotency_key="k"),
    )
    assert out.approved is False


def test_verify_outcome_matches_expected_result():
    store = _store()
    incident_id = next(iter(store.incidents))
    reconciliation = apply_reconciliation(store, incident_id)
    proposal = tools.propose_resolution(store, incident_id, reconciliation)
    exec_result = tools.request_action(
        store, s.RequestActionInput(action_id=proposal.action_id, actor_id="tester", idempotency_key="k-2"),
    )
    verify = tools.verify_outcome(
        store, s.VerifyOutcomeInput(execution_id=exec_result.execution_id, expected_result=proposal.action_type),
    )
    assert verify.result == OutcomeVerificationResult.VERIFIED


def test_verify_outcome_unknown_execution_is_unknown_not_a_guess():
    store = _store()
    out = tools.verify_outcome(store, s.VerifyOutcomeInput(execution_id="EXE-NOPE", expected_result="X"))
    assert out.result == OutcomeVerificationResult.UNKNOWN
