from pathlib import Path

from conclave.pilot import load_phase7_pilot_dataset, run_phase7_pilot


def test_phase7_dataset_has_required_breadth() -> None:
    dataset = load_phase7_pilot_dataset()

    assert len(dataset.cases) == 34
    assert sum("material" in case.coverage for case in dataset.cases) >= 5
    assert sum("timeout" in case.coverage for case in dataset.cases) >= 3
    assert sum("malformed_output" in case.coverage for case in dataset.cases) == 2
    assert sum("tie_breaker" in case.coverage for case in dataset.cases) >= 4


def test_phase7_pilot_passes_all_expected_outcomes(tmp_path: Path) -> None:
    report = run_phase7_pilot(output_dir=tmp_path)
    summary = report["summary"]

    assert summary["case_count"] == 34
    assert summary["expected_outcomes_passed"] == 34
    assert summary["reliability_rate"] == 1.0
    assert summary["completed_results"] == 31
    assert summary["expected_terminal_cases"] == 3
    assert summary["recovered_cases"] == 1
    assert summary["audit_verifications_passed"] == 31
    assert summary["terminal_audit_verifications_passed"] == 3
    assert summary["all_audit_traces_passed"] == 34
    assert summary["independence_checks_passed"] == 34
    assert summary["snapshot_consistency_checks_passed"] == 34
    assert summary["evidence_traceability_checks_passed"] == 31
    assert summary["clarity_heuristic_checks_passed"] == 31
    assert report["routing"]["counts"] == {
        "a_only": 6,
        "ab_agreement": 12,
        "c_tie_broken": 6,
        "cross_review_resolved": 7,
    }
    assert report["directional_evaluation_metrics"]["candidate_count"] == 31
    assert report["provider_attempt_metrics"]["counts"] == {
        "invalid_output": 2,
        "permanent_failure": 1,
        "retryable_failure": 4,
        "succeeded": 96,
    }
    assert (tmp_path / "phase7-pilot-results.json").is_file()
