from conclave.contracts.validation import validate_contract_package


def test_draft_contract_package_is_internally_valid() -> None:
    report = validate_contract_package()

    assert report.request_count == 4
    assert report.result_count == 4
    assert report.feedback_count == 1
    assert report.comparator_case_count == 5
