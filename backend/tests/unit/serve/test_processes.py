from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.serve.processes import PROCESSES_PER_CONTAINER_ENV, processes_per_container


@dataclass
class ProcessCountCase:
    name: str
    value: str | None
    """What the environment holds; ``None`` leaves the value unset."""

    expected: int


PROCESS_COUNT_CASES = [
    ProcessCountCase(name="gunicorn_set_the_count", value="4", expected=4),
    ProcessCountCase(name="a_process_gunicorn_did_not_start_runs_alone", value=None, expected=1),
    ProcessCountCase(name="zero_is_not_a_count", value="0", expected=1),
    ProcessCountCase(name="a_negative_value_is_not_a_count", value="-2", expected=1),
    ProcessCountCase(name="text_is_not_a_count", value="four", expected=1),
]


@pytest.mark.parametrize("case", PROCESS_COUNT_CASES, ids=[case.name for case in PROCESS_COUNT_CASES])
def test_processes_per_container(case: ProcessCountCase, monkeypatch: pytest.MonkeyPatch) -> None:
    if case.value is None:
        monkeypatch.delenv(PROCESSES_PER_CONTAINER_ENV, raising=False)
    else:
        monkeypatch.setenv(PROCESSES_PER_CONTAINER_ENV, case.value)

    assert processes_per_container() == case.expected
