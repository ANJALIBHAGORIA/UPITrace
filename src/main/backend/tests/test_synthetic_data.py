"""Phase 1 acceptance tests: synthetic data generator."""
import json
import tempfile
from pathlib import Path

from src.main.backend.scripts.generate_synthetic_data import (
    SCENARIO_BUILDERS,
    generate,
    write_all,
)

EXPECTED_CATEGORIES = {
    "BOTH_CONFIRMED",
    "DEBIT_NO_MERCHANT_CONFIRM",
    "BOTH_PENDING",
    "MISSING_NOTIFICATION",
    "NOTIFICATION_DELIVERED_NOT_PROCESSED",
    "PROVIDER_BANK_CONFLICT",
    "DUPLICATE_NOTIFICATION",
    "DUPLICATE_PAYMENT_ATTEMPT",
    "REFUND_REQUESTED_UNVERIFIED",
    "REVERSAL_MISSING_OR_PENDING",
    "ORDER_EXPIRED_OR_CANCELLED",
    "INSUFFICIENT_EVIDENCE",
}


def test_generates_at_least_30_incidents():
    data = generate(seed=42)
    assert len(data["incidents"]) >= 30


def test_all_12_scenario_categories_present():
    data = generate(seed=42)
    categories = {gt.scenario_category for gt in data["ground_truth"]}
    assert categories == EXPECTED_CATEGORIES
    assert len(SCENARIO_BUILDERS) == 12


def test_every_category_has_at_least_one_incident():
    data = generate(seed=42)
    counts: dict[str, int] = {}
    for gt in data["ground_truth"]:
        counts[gt.scenario_category] = counts.get(gt.scenario_category, 0) + 1
    assert all(count >= 1 for count in counts.values())
    assert min(counts.values()) * len(counts) <= len(data["incidents"])


def test_reproducible_given_fixed_seed():
    data1 = generate(seed=42)
    data2 = generate(seed=42)
    ids1 = [i.incident_id for i in data1["incidents"]]
    ids2 = [i.incident_id for i in data2["incidents"]]
    assert ids1 == ids2

    titles1 = [i.title for i in data1["incidents"]]
    titles2 = [i.title for i in data2["incidents"]]
    assert titles1 == titles2


def test_different_seed_can_change_merchant_assignment():
    # Not a strict requirement, but confirms the RNG is actually wired in
    # (merchant choice depends on rng) rather than being hardcoded.
    data_a = generate(seed=1)
    data_b = generate(seed=2)
    merchants_a = [i.merchant_id for i in data_a["incidents"]]
    merchants_b = [i.merchant_id for i in data_b["incidents"]]
    assert merchants_a != merchants_b


def test_incident_ids_are_unique():
    data = generate(seed=42)
    ids = [i.incident_id for i in data["incidents"]]
    assert len(ids) == len(set(ids))


def test_every_incident_evidence_id_resolves_to_a_real_evidence_record():
    data = generate(seed=42)
    real_evidence_ids = {e.evidence_id for e in data["evidence_records"]}
    for incident in data["incidents"]:
        for evidence_id in incident.evidence_ids:
            assert evidence_id in real_evidence_ids, (
                f"Incident {incident.incident_id} references missing evidence {evidence_id}"
            )


def test_every_source_event_references_a_real_incident():
    data = generate(seed=42)
    real_incident_ids = {i.incident_id for i in data["incidents"]}
    for event in data["source_events"]:
        assert event.incident_id in real_incident_ids


def test_every_evidence_record_references_a_real_incident():
    data = generate(seed=42)
    real_incident_ids = {i.incident_id for i in data["incidents"]}
    for evidence in data["evidence_records"]:
        assert evidence.incident_id in real_incident_ids


def test_payment_attempt_id_on_incident_resolves_when_present():
    data = generate(seed=42)
    real_pa_ids = {pa.payment_attempt_id for pa in data["payment_attempts"]}
    for incident in data["incidents"]:
        if incident.payment_attempt_id is not None:
            assert incident.payment_attempt_id in real_pa_ids


def test_every_incident_has_exactly_one_ground_truth_record():
    data = generate(seed=42)
    incident_ids = [i.incident_id for i in data["incidents"]]
    gt_ids = [gt.incident_id for gt in data["ground_truth"]]
    assert sorted(incident_ids) == sorted(gt_ids)


def test_insufficient_evidence_scenarios_are_marked_unresolvable():
    data = generate(seed=42)
    unresolvable = [gt for gt in data["ground_truth"] if gt.scenario_category == "INSUFFICIENT_EVIDENCE"]
    assert unresolvable, "expected at least one INSUFFICIENT_EVIDENCE case"
    assert all(gt.is_resolvable is False for gt in unresolvable)


def test_resolvable_scenarios_are_marked_resolvable():
    data = generate(seed=42)
    resolvable = [gt for gt in data["ground_truth"] if gt.scenario_category != "INSUFFICIENT_EVIDENCE"]
    assert all(gt.is_resolvable is True for gt in resolvable)


def test_runbooks_are_generated_and_labelled_synthetic():
    data = generate(seed=42)
    assert len(data["runbooks"]) > 0
    assert all(rb.source == "SYNTHETIC_DEMO" for rb in data["runbooks"])


def test_write_all_separates_ground_truth_from_production_data():
    data = generate(seed=42)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        import src.main.backend.scripts.generate_synthetic_data as gen_module

        original_synthetic_dir = gen_module.SYNTHETIC_DIR
        original_evaluation_dir = gen_module.EVALUATION_DIR
        try:
            gen_module.SYNTHETIC_DIR = tmp_path / "synthetic"
            gen_module.EVALUATION_DIR = tmp_path / "evaluation"
            write_all(data)

            assert (tmp_path / "synthetic" / "incidents.json").exists()
            assert (tmp_path / "evaluation" / "ground_truth.json").exists()
            # Ground truth file must not be reachable under the synthetic dir.
            assert not (tmp_path / "synthetic" / "ground_truth.json").exists()

            incidents_payload = json.loads((tmp_path / "synthetic" / "incidents.json").read_text())
            for record in incidents_payload:
                assert "expected_reconciliation_status" not in record
                assert "expected_safe_next_action" not in record
        finally:
            gen_module.SYNTHETIC_DIR = original_synthetic_dir
            gen_module.EVALUATION_DIR = original_evaluation_dir


def test_provider_bank_conflict_keeps_both_statuses_visible():
    data = generate(seed=42)
    conflict_incidents = [
        i for i in data["incidents"] if "Conflicting status" in i.title
    ]
    assert conflict_incidents
    for incident in conflict_incidents:
        related_events = [e for e in data["source_events"] if e.incident_id == incident.incident_id]
        statuses = {e.source_status for e in related_events}
        assert len(statuses) >= 2, "conflict scenario should preserve both disagreeing statuses"
