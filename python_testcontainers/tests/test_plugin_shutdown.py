import pytest

PLUGIN_NAME = "pytest-infrahub-performance-test"


def test_reporting_runs_after_the_stack_teardown(pytestconfig: pytest.Config) -> None:
    """Result reporting must not sit in front of the compose stack teardown.

    Class and session fixtures of an interrupted run are torn down by pytest's own
    pytest_sessionfinish, so a plugin that reports before it holds the stack hostage to
    however long reporting takes.
    """
    impls = pytestconfig.pluginmanager.hook.pytest_sessionfinish.get_hookimpls()
    execution_order = [impl.plugin_name for impl in reversed(impls)]

    assert execution_order.index("runner") < execution_order.index(PLUGIN_NAME)
