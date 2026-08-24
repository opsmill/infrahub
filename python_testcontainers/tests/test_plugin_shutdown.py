import pytest

from infrahub_testcontainers.performance_test import InfrahubPerformanceTest
from infrahub_testcontainers.plugin import pytest_sessionfinish

PLUGIN_NAME = "pytest-infrahub-performance-test"


class InterruptedPerformanceTest(InfrahubPerformanceTest):
    """Stands in for a report upload that a cancelled CI job signals mid-flight."""

    def send_results(self) -> None:
        raise KeyboardInterrupt


class RecordingPerformanceTest(InfrahubPerformanceTest):
    finalized: bool = False

    def finalize(self, session: pytest.Session) -> None:
        self.finalized = True

    def fetch_metrics(self) -> None:
        return


def test_reporting_runs_after_the_stack_teardown(pytestconfig: pytest.Config) -> None:
    """Result reporting must not sit in front of the compose stack teardown.

    Class and session fixtures of an interrupted run are torn down by pytest's own
    pytest_sessionfinish, so a plugin that reports before it holds the stack hostage to
    however long reporting takes.
    """
    impls = pytestconfig.pluginmanager.hook.pytest_sessionfinish.get_hookimpls()
    execution_order = [impl.plugin_name for impl in reversed(impls)]

    assert execution_order.index("runner") < execution_order.index(PLUGIN_NAME)


def test_finalize_swallows_an_interrupt(request: pytest.FixtureRequest) -> None:
    performance_test = InterruptedPerformanceTest(results_url="http://localhost")
    performance_test.initialize(name="test_finalize_swallows_an_interrupt")

    performance_test.finalize(session=request.session)


def test_interrupted_session_is_not_reported(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    performance_test = RecordingPerformanceTest(results_url="http://localhost")
    monkeypatch.setattr(request.config.option, "infrahub_performance_report", True)
    monkeypatch.setattr(request.session, "infrahub_performance_test", performance_test)

    pytest_sessionfinish(session=request.session, exitstatus=pytest.ExitCode.INTERRUPTED)
    assert not performance_test.finalized

    pytest_sessionfinish(session=request.session, exitstatus=pytest.ExitCode.OK)
    assert performance_test.finalized
