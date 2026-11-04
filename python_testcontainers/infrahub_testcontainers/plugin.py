from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .performance_test import DEFAULT_UPLOAD_RETRIES, InfrahubPerformanceTest

if TYPE_CHECKING:
    import _pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("infrahub-performance-test")

    group.addoption(
        "--deployment-type",
        action="store",
        dest="infrahub_deployment_type",
        default=None,
        metavar="INFRAHUB_DEPLOYMENT_TYPE",
        help="Type of deployment to use (default: None, options: cluster)",
    )

    group.addoption(
        "--performance-result-address",
        action="store",
        dest="infrahub_performance_test_result_address",
        default="https://webhook.site/25802839-4b34-433e-9dc4-59623cd73c80",
        metavar="INFRAHUB_PERFORMANCE_TEST_RESULT_ADDRESS",
        help="Address to send the results of the performance test (default: %(default)s)",
    )
    group.addoption(
        "--performance-result-compress",
        action="store_true",
        dest="infrahub_performance_result_compress",
        default=False,
        help="Send the results gzip-compressed, with Content-Encoding: gzip (default: %(default)s)",
    )
    group.addoption(
        "--performance-result-retries",
        action="store",
        type=int,
        dest="infrahub_performance_result_retries",
        default=DEFAULT_UPLOAD_RETRIES,
        metavar="INFRAHUB_PERFORMANCE_RESULT_RETRIES",
        help="How many times to retry sending the results after a connection error, a timeout, "
        "a 408, a 429 or a 5xx answer (default: %(default)s)",
    )
    group.addoption(
        "--performance-result-required",
        action="store_true",
        dest="infrahub_performance_result_required",
        default=False,
        help="Fail a passing session when its results cannot be stored (default: %(default)s)",
    )
    group.addoption(
        "--performance-result-file",
        action="store",
        dest="infrahub_performance_result_file",
        default=None,
        metavar="INFRAHUB_PERFORMANCE_RESULT_FILE",
        help="Also write the results to this file, uncompressed, before sending them (default: %(default)s)",
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
    result_file = session.config.getoption("infrahub_performance_result_file")
    session.infrahub_performance_test = InfrahubPerformanceTest(
        results_url=session.config.getoption("infrahub_performance_test_result_address"),
        compress=session.config.getoption("infrahub_performance_result_compress"),
        retries=session.config.getoption("infrahub_performance_result_retries"),
        result_file=Path(result_file) if result_file else None,
    )


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """whole test run finishes.

    Runs last so that reporting stays behind the fixture teardown that stops the compose
    stack. On an interrupted session that teardown happens from pytest's own
    pytest_sessionfinish, and a CI runner allows only a few seconds between the cancel
    signal and the kill: anything ahead of the teardown can cost the stack its shutdown.
    """
    if not session.config.getoption("infrahub_performance_report"):
        return

    if exitstatus == pytest.ExitCode.INTERRUPTED:
        # An interrupted run measured only part of the suite, and the seconds left before
        # the runner kills the process are better spent shutting the stack down.
        return

    session.infrahub_performance_test.finalize(session=session)

    if (
        session.infrahub_performance_test.report_error
        and session.config.getoption("infrahub_performance_result_required")
        and session.exitstatus == pytest.ExitCode.OK
    ):
        # pytest exits with the status the session holds once this hook returns.
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # noqa: ARG001
    """Fetch metrics at each test teardown because there's no better hook...

    pytest_sessionfinish() is executed after fixtures has been finalized and pytest_fixture_post_finalizer() is too late."""
    if not item.config.getoption("infrahub_performance_report"):
        return

    item.session.infrahub_performance_test.fetch_metrics()


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("infrahub_performance_use_backup") and config.getoption("infrahub_performance_create_backup"):
        raise pytest.UsageError("--performance-use-backup and --performance-create-backup are mutually exclusive")
    if config.getoption("infrahub_performance_result_retries") < 0:
        raise pytest.UsageError("--performance-result-retries cannot be negative")

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
        f"{measurement.name} ({measurement.context}): {measurement.value} {measurement.unit.value}"
        for measurement in performance_test.measurements
    ]
    terminalreporter.write("\n" + "\n".join(report) + "\n")
    if performance_test.report_error:
        terminalreporter.write_line(
            f"Performance results were not stored: {performance_test.report_error}", red=True, bold=True
        )


@pytest.fixture(scope="session")
def perf_test(request: pytest.FixtureRequest) -> InfrahubPerformanceTest:
    return request.session.infrahub_performance_test
