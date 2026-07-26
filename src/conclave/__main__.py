import argparse

from conclave.contracts.validation import validate_contract_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Conclave development utilities")
    parser.add_argument(
        "command",
        choices=["validate-fixtures"],
        help="Validate the local draft contracts and fixtures.",
    )
    args = parser.parse_args()

    if args.command == "validate-fixtures":
        report = validate_contract_package()
        print(
            "Validated "
            f"{report.request_count} requests, "
            f"{report.result_count} results, "
            f"{report.feedback_count} feedback records, and "
            f"{report.comparator_case_count} comparator cases."
        )


if __name__ == "__main__":
    main()
