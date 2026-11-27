from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from infrahub.telemetry.constants import WorkflowRunState
from infrahub.telemetry.models import TelemetryWorkflowRunData


@dataclass
class PartlyFilledRowCase:
    name: str
    state: WorkflowRunState | None
    runs: int | None
    run_seconds: int | None


PARTLY_FILLED_ROW_CASES: list[PartlyFilledRowCase] = [
    PartlyFilledRowCase(name="state_without_counts", state=WorkflowRunState.COMPLETED, runs=None, run_seconds=None),
    PartlyFilledRowCase(name="counts_without_state", state=None, runs=3, run_seconds=4),
    PartlyFilledRowCase(name="run_seconds_missing", state=WorkflowRunState.FAILED, runs=3, run_seconds=None),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in PARTLY_FILLED_ROW_CASES])
def test_workflow_run_row_rejects_a_partly_filled_row(case: PartlyFilledRowCase) -> None:
    with pytest.raises(ValidationError, match="all set or all null"):
        TelemetryWorkflowRunData(
            workflow="generator-run", state=case.state, runs=case.runs, run_seconds=case.run_seconds
        )


def test_workflow_run_row_serialises_a_failed_read_as_three_nulls() -> None:
    row = TelemetryWorkflowRunData(workflow="generator-run")

    assert row.model_dump(mode="json") == {
        "workflow": "generator-run",
        "state": None,
        "runs": None,
        "run_seconds": None,
    }


def test_workflow_run_row_serialises_the_end_state_as_text() -> None:
    row = TelemetryWorkflowRunData(workflow="generator-run", state=WorkflowRunState.CRASHED, runs=2, run_seconds=3)

    assert row.model_dump(mode="json") == {
        "workflow": "generator-run",
        "state": "CRASHED",
        "runs": 2,
        "run_seconds": 3,
    }
