from typing import Dict, List, Optional, Tuple

from infrahub_sdk.client import Config as InfrahubClientConfig
from infrahub_sdk.client import InfrahubClientSync
from infrahub_sdk.node import InfrahubNodeSync
from pytest import Config, Item, Session, TestReport

from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp

OUTCOME_TO_CONCLUSION_MAP = {"passed": "success", "failed": "failure", "skipped": "failure"}
OUTCOME_TO_SEVERITY_MAP = {"passed": "success", "failed": "error", "skipped": "warning"}


class InfrahubBackendPlugin:
    def __init__(self, config: InfrahubClientConfig, repository_id: str, proposed_change_id: str) -> None:
        self.client = InfrahubClientSync(config=config)

        self.repository_id = repository_id
        self.proposed_change_id = proposed_change_id

        self.proposed_change: InfrahubNodeSync
        self.validator: InfrahubNodeSync
        self.checks: Dict[str, InfrahubNodeSync] = {}

    def get_repository_validator(self) -> Tuple[InfrahubNodeSync, bool]:
        """Return the existing RepositoryValidator for the ProposedChange or create a new one."""
        validator_name = "Repository Tests Validator"

        for relationship in self.proposed_change.validations.peers:
            existing_validator = relationship.peer

            if (
                existing_validator.typename == InfrahubKind.REPOSITORYVALIDATOR
                and existing_validator.repository.id == self.repository_id
                and existing_validator.label.value == validator_name
            ):
                return existing_validator, False

        validator = self.client.create(
            kind=InfrahubKind.REPOSITORYVALIDATOR,
            data={"label": validator_name, "proposed_change": self.proposed_change, "repository": self.repository_id},
        )
        validator.save()

        return validator, True

    def pytest_collection_modifyitems(self, session: Session, config: Config, items: List[Item]) -> None:  # pylint: disable=unused-argument
        """This function is called after item collection and gives the opportunity to work on the collection before sending the items for testing."""
        # TODO: Filter tests according to what's been requested
        # TODO: Re-order tests: sanity -> unit -> integration

    def pytest_collection_finish(self, session: Session) -> None:  # pylint: disable=unused-argument
        """This function is called when tests have been collected and modified, meaning they are ready to be run."""
        self.proposed_change = self.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=self.proposed_change_id)
        self.proposed_change.validations.fetch()

        self.validator, is_new_validator = self.get_repository_validator()
        # Workaround for https://github.com/opsmill/infrahub/issues/2184
        if not is_new_validator:
            self.validator.checks.fetch()
            for check in self.validator.checks.peers:
                self.checks[check.peer.origin.value] = check.peer

    def pytest_runtestloop(self, session: Session) -> Optional[object]:  # pylint: disable=unused-argument,useless-return
        """This function is called when the test loop is being run."""
        self.validator.conclusion.value = "unknown"
        self.validator.state.value = "in_progress"
        self.validator.started_at.value = Timestamp().to_string()
        self.validator.completed_at.value = ""

        return None

    def pytest_runtest_setup(self, item: Item) -> None:
        """Create a StandardCheck for each test item to later record its details.

        If a check already exists, reset it to its default values.
        """
        check = self.checks.get(item.nodeid, None)
        if check:
            check.message.value = ""
            check.conclusion.value = "unknown"
            check.severity.value = "info"
            check.created_at.value = Timestamp().to_string()
        else:
            check = self.client.create(
                kind=InfrahubKind.STANDARDCHECK,
                data={
                    "name": item.name,
                    "origin": item.nodeid,
                    "kind": "TestReport",
                    "validator": self.validator.id,
                    "created_at": Timestamp().to_string(),
                    "severity": "info",
                },
            )
            self.checks[item.nodeid] = check

        check.save()

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """This function is called 3 times per test: setup, call, teardown."""
        if report.when != "call":
            return

        check = self.checks[report.nodeid]
        check.message.value = report.longreprtext
        check.severity.value = OUTCOME_TO_SEVERITY_MAP[report.outcome]
        check.conclusion.value = OUTCOME_TO_CONCLUSION_MAP[report.outcome]
        check.save()

    def pytest_sessionfinish(self, session: Session) -> None:  # pylint: disable=unused-argument
        """Set the final RepositoryValidator details after completing the test session."""
        conclusion = "success"

        for check in self.checks.values():
            if check.conclusion.value == "failure":
                conclusion = check.conclusion.value
                break

        self.validator.state.value = "completed"
        self.validator.completed_at.value = Timestamp().to_string()
        self.validator.conclusion.value = conclusion
        self.validator.save()
