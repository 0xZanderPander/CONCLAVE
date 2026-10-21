"""Chimera conformance oracle.

The 34 Phase 7 cases were captured from the pre-pack engine (commit 5bfb504,
branch agent/initial-conclave) as a complete ledger dump: every result
document, every stored reviewer payload, every domain event and every audit
event. The generalized engine running the ``chimera`` pack must reproduce the
capture byte-for-byte.

Do not regenerate the golden file to make a refactor pass. If the capture must
change, that is a design finding and needs an explicit decision (AGENTS.md).
"""

import json
from pathlib import Path

import pytest

from conclave.paths import design_fixtures_root
from conclave.pilot.runner import load_phase7_pilot_dataset, run_phase7_pilot

GOLDEN_PATH = design_fixtures_root() / "phase7-golden" / "chimera-ledger-golden.json"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@pytest.fixture(scope="module")
def captured() -> dict[str, dict]:
    capture: dict[str, dict] = {}
    run_phase7_pilot(ledger_capture=capture)
    return capture


@pytest.fixture(scope="module")
def golden() -> dict[str, dict]:
    with GOLDEN_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def test_golden_covers_every_phase7_case(golden: dict[str, dict]) -> None:
    dataset = load_phase7_pilot_dataset()
    assert sorted(golden) == sorted(case.case_id for case in dataset.cases)
    assert len(golden) == 34


@pytest.mark.parametrize("case_id", [f"phase7-{index:03d}" for index in range(1, 35)])
def test_chimera_reproduces_golden_ledger(
    case_id: str,
    captured: dict[str, dict],
    golden: dict[str, dict],
) -> None:
    expected = golden[case_id]
    actual = captured[case_id]
    # Field-by-field first so a failure names the drifted section.
    for field in expected:
        assert _canonical(actual[field]) == _canonical(expected[field]), (
            f"{case_id}: {field} differs from the golden capture"
        )
    assert _canonical(actual) == _canonical(expected)


def test_golden_file_is_canonical(tmp_path: Path) -> None:
    text = GOLDEN_PATH.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
