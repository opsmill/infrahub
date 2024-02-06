import collections
import datetime
import enum
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.pytest_plugin.loader import InfrahubYamlFile
from infrahub_sdk.pytest_plugin.utils import load_repository_config
from pytest import Collector, Item, Session, TestReport

TEST_FILE_PREFIX = "test_"
TEST_FILE_SUFFIXES = [".yml", ".yaml"]


class TestOutcome(enum.Enum):
    """Enum for the different pytest outcomes."""

    ERROR = "error"
    FAILED = "failed"
    PASSED = "passed"
    SKIPPED = "skipped"
    XFAILED = "xfailed"
    XPASSED = "xpassed"


class InfrahubBackendPlugin:
    def __init__(self, directory: Path, client: InfrahubClient) -> None:
        self.directory = directory
        self.client = client

        # This will allow use to render a proper report
        self.session_start: float
        self.session_finish: float
        self.session_duration: float
        self.report = ""
        self.reports: Dict[TestOutcome, List] = collections.defaultdict(list)

    def get_report_header(self) -> str:
        now = datetime.datetime.now(tz=datetime.UTC).isoformat()
        return f"# Tests Report\n\nGenerated at {now}\n"

    def get_report_summary(self) -> str:
        text = ""
        total_count = 0

        for outcome in (o for o in TestOutcome if o in self.reports):
            count = len(self.reports[outcome])
            total_count += count
            text += f"- {count} {outcome.value}\n".lower()

        summary = "## Summary\n\n"
        summary += f"{total_count} tests ran in {self.session_duration:.2f} seconds"

        return summary + "\n\n" + text

    def get_report_results(self) -> str:
        outcomes = {}

        for outcome in (o for o in TestOutcome if o in self.reports):
            reports_by_file: Dict[str, List] = collections.defaultdict(list)

            for report in self.reports[outcome]:
                test_file = report.location[0]
                reports_by_file[test_file].append(report)

            outcomes[outcome] = reports_by_file

        results = ""

        for outcome, reports_by_file in outcomes.items():
            outcome_text = outcome.value

            results += f"## {len(self.reports[outcome])} {outcome_text}\n\n".lower()

            for test_file, reports in reports_by_file.items():
                results += f"### {test_file}\n\n"

                for report in reports:
                    test_function = report.location[2]

                    if outcome is TestOutcome.ERROR:
                        results += f"`{outcome.value} at {report.when} of {test_function}`"
                    else:
                        results += f"`{test_function}`"
                    results += f" {report.duration:.2f}s\n"

                    if outcome in (TestOutcome.ERROR, TestOutcome.FAILED):
                        results += f"\n```\n{report.longreprtext}\n```\n"

                    results += "\n"

        return results

    def pytest_sessionstart(self, session: Session) -> None:
        self.session_start = time.time()

        session.infrahub_config_path = self.directory / ".infrahub.yml"  # type: ignore[attr-defined]
        if session.infrahub_config_path.is_file():  # type: ignore[attr-defined]
            session.infrahub_repo_config = load_repository_config(repo_config_file=session.infrahub_config_path)  # type: ignore[attr-defined]

    def pytest_sessionfinish(self, session: Session) -> None:  # pylint: disable=unused-argument
        self.session_finish = time.time()
        self.session_duration = self.session_finish - self.session_start

        self.report += self.get_report_header() + "\n" + self.get_report_summary() + "\n" + self.get_report_results()

    def pytest_collect_file(self, parent: Union[Collector, Item], file_path: Path) -> Optional[InfrahubYamlFile]:
        if file_path.suffix in TEST_FILE_SUFFIXES and file_path.name.startswith(TEST_FILE_PREFIX):
            return InfrahubYamlFile.from_parent(parent, path=file_path)
        return None

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        if report.when in ("setup", "teardown"):
            if report.failed:
                self.reports[TestOutcome.ERROR].append(report)
            if report.skipped:
                self.reports[TestOutcome.SKIPPED].append(report)
            # Ignore successful setup/teardown from report
            return

        if hasattr(report, "wasxfail"):
            if report.skipped:
                self.reports[TestOutcome.XFAILED].append(report)
            if report.passed:
                self.reports[TestOutcome.XPASSED].append(report)
            return

        if report.when == "call":
            if report.passed:
                self.reports[TestOutcome.PASSED].append(report)
            if report.skipped:
                self.reports[TestOutcome.SKIPPED].append(report)
            if report.failed:
                self.reports[TestOutcome.FAILED].append(report)
