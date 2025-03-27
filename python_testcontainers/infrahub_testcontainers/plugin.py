from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .performance_test import InfrahubPerformanceTest

if TYPE_CHECKING:
    import _pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("infrahub-performance-test")

    group.addoption(
        "--performance-result-address",
        action="store",
        dest="infrahub_performance_test_result_address",
        default="https://webhook.site/25802839-4b34-433e-9dc4-59623cd73c80",
        metavar="INFRAHUB_PERFORMANCE_TEST_RESULT_ADDRESS",
        help="Address to send the results of the performance test (default: %(default)s)",
    )
    group.addoption(
        "--performance-backup",
        action="store",
        dest="infrahub_performance_backup",
        default="neo4j_database.db",
        metavar="INFRAHUB_PERFORMANCE_BACKUP",
        help="Name of the backup to use (default: %(default)s)",
    )
    group.addoption(
        "--performance-backup-location",
        action="store",
        dest="infrahub_performance_backup_location",
        metavar="INFRAHUB_PERFORMANCE_BACKUP_LOCATION",
        help="Location of the backup to use (default: %(default)s)",
    )
    group.addoption(
        "--performance-create-backup",
        action="store_true",
        default=False,
        dest="infrahub_performance_create_backup",
        help="Generate a backup of the database (default: %(default)s)",
    )
    group.addoption(
        "--performance-use-backup",
        action="store_true",
        default=False,
        dest="infrahub_performance_use_backup",
        help="Use a backup of the database and skip all tests that creates data (default: %(default)s)",
    )
    group.addoption(
        "--performance-report",
        action="store_true",
        dest="infrahub_performance_report",
        default=False,
        help="Display performance report at the end of the test run",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    use_backup_skip = pytest.mark.skip(reason="load data from backup")
    no_create_backup_skip = pytest.mark.skip(reason="no need to create a backup")
    no_load_backup_skip = pytest.mark.skip(reason="no need to load a backup")

    use_backup = config.getoption("infrahub_performance_use_backup")
    create_backup = config.getoption("infrahub_performance_create_backup")

    for item in items:
        has_create_backup_marker = bool(
            [True for marker in item.own_markers if marker.name == "performance_create_backup"]
        )
        has_load_backup_marker = bool([True for marker in item.own_markers if marker.name == "performance_load_backup"])
        has_load_data_marker = bool([True for marker in item.own_markers if marker.name == "performance_load_data"])

        if has_create_backup_marker and not create_backup:
            item.add_marker(no_create_backup_skip)
        if has_load_backup_marker and not use_backup:
            item.add_marker(no_load_backup_skip)
        if has_load_data_marker and use_backup:
            item.add_marker(use_backup_skip)


def pytest_sessionstart(session: pytest.Session) -> None:
    session.infrahub_performance_test = InfrahubPerformanceTest(
        results_url=session.config.getoption("infrahub_performance_test_result_address")
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    """whole test run finishes."""
    if not session.config.getoption("infrahub_performance_report"):
        return

    session.infrahub_performance_test.finalize(session=session)


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # noqa: ARG001
    """Fetch metrics at each test teardown because there's no better hook...
    pytest_sessionfinish() is executed after fixtures has been finalized and pytest_fixture_post_finalizer() is too late"""
    if not item.config.getoption("infrahub_performance_report"):
        return

    item.session.infrahub_performance_test.fetch_metrics()


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("infrahub_performance_use_backup") and config.getoption("infrahub_performance_create_backup"):
        raise pytest.UsageError("--performance-use-backup and --performance-create-backup are mutually exclusive")

    config.addinivalue_line("markers", "performance_create_backup: Create a backup of the database")
    config.addinivalue_line("markers", "performance_load_backup: Load the backup of the database")
    config.addinivalue_line("markers", "performance_load_data: Load initial data into the database")


def pytest_terminal_summary(
    terminalreporter: _pytest.terminal.TerminalReporter,
    exitstatus: int,  # noqa: ARG001
    config: pytest.Config,
) -> None:
    if not config.getoption("infrahub_performance_report"):
        return

    performance_test = terminalreporter._session.infrahub_performance_test

    report = [
        f"{measurement.name}: {measurement.value} {measurement.unit.value}"
        for measurement in performance_test.measurements
    ]
    terminalreporter.write("\n" + "\n".join(report) + "\n")


@pytest.fixture(scope="session")
def perf_test(request: pytest.FixtureRequest) -> InfrahubPerformanceTest:
    return request.session.infrahub_performance_test
