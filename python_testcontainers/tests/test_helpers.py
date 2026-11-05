from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

INNER_TEST = """
import json
from pathlib import Path

import pytest

from infrahub_testcontainers.helpers import TestInfrahubDocker

FAILING_STEP = {failing_step!r}
CALLS_FILE = Path(__file__).with_name("compose_calls.json")


class RecordingCompose:
    def __init__(self) -> None:
        self.calls = []

    def _record(self, step):
        self.calls.append(step)
        CALLS_FILE.write_text(json.dumps(self.calls))
        if step == FAILING_STEP:
            raise RuntimeError(f"{{step}} failed")

    def start(self):
        self._record("start")

    def get_services_port(self):
        self._record("get_services_port")
        return {{"server": 8000}}

    def get_logs(self, *services):
        self._record("get_logs")
        return "", ""

    def stop(self):
        self._record("stop")


class TestStack(TestInfrahubDocker):
    @pytest.fixture(scope="class")
    def infrahub_compose(self):
        return RecordingCompose()

    def test_reads_the_ports(self, infrahub_app):
        assert infrahub_app == {{"server": 8000}}
"""


@dataclass
class StackCleanupTestCase:
    name: str
    failing_step: str | None
    expected_calls: list[str]
    expected_outcomes: dict[str, int]


STACK_CLEANUP_TEST_CASES: list[StackCleanupTestCase] = [
    StackCleanupTestCase(
        name="start_fails",
        failing_step="start",
        expected_calls=["start", "get_logs", "stop"],
        expected_outcomes={"errors": 1},
    ),
    StackCleanupTestCase(
        name="port_lookup_fails",
        failing_step="get_services_port",
        expected_calls=["start", "get_services_port", "stop"],
        expected_outcomes={"errors": 1},
    ),
    StackCleanupTestCase(
        name="tests_pass",
        failing_step=None,
        expected_calls=["start", "get_services_port", "stop"],
        expected_outcomes={"passed": 1},
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in STACK_CLEANUP_TEST_CASES],
)
def test_infrahub_app_stops_the_stack(test_case: StackCleanupTestCase, pytester: pytest.Pytester) -> None:
    pytester.makepyfile(INNER_TEST.format(failing_step=test_case.failing_step))

    result = pytester.runpytest_subprocess()

    result.assert_outcomes(**test_case.expected_outcomes)
    assert json.loads((pytester.path / "compose_calls.json").read_text()) == test_case.expected_calls
