from typing import Dict, List, Optional

from infrahub_sdk.client import Config as InfrahubClientConfig
from infrahub_sdk.client import InfrahubClientSync
from infrahub_sdk.node import InfrahubNodeSync
from pytest import Config, Item, Session, TestReport

from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp

OUTCOME_TO_CONCLUSION_MAP = {"passed": "success", "failed": "failure", "skipped": "unknown"}
OUTCOME_TO_SEVERITY_MAP = {"passed": "info", "failed": "critical", "skipped": "warning"}


class InfrahubBackendPlugin:
    def __init__(self, config: InfrahubClientConfig, repository_id: str, proposed_change_id: str) -> None:
        self.client = InfrahubClientSync(config=config)

        self.repository_id = repository_id
        self.proposed_change = self.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=proposed_change_id)

        self.validator: InfrahubNodeSync = None
        self.checks: Dict[str, InfrahubNodeSync] = {}

    def get_repository_validator(self) -> InfrahubNodeSync:
        """Return the existing RepositoryValidator for the ProposedChange or create a new one."""
        self.proposed_change.validations.fetch()

        validator = None
        validator_name = "Repository Tests Validator"
        for relationship in self.proposed_change.validations.peers:
            existing_validator = relationship.peer

            if (
                existing_validator.typename == InfrahubKind.REPOSITORYVALIDATOR
                and existing_validator.repository.id == self.repository_id
                and existing_validator.label.value == validator_name
            ):
                validator = existing_validator

        if not validator:
            validator = self.client.create(
                kind=InfrahubKind.REPOSITORYVALIDATOR,
                data={
                    "label": validator_name,
                    "proposed_change": self.proposed_change,
                    "repository": self.repository_id,
                },
            )
            validator.save()

        return validator

    def pytest_collection_modifyitems(self, session: Session, config: Config, items: List[Item]) -> None:  # pylint: disable=unused-argument
        """This function is called after item collection and gives the opportunity to work on the collection before sending the items for testing."""
        # FIXME: Does this really belongs here?
        # FIXME: Fetch checks if the validator already has some
        self.validator = self.get_repository_validator()
        # TODO: Filter tests according to what's been requested
        # TODO: Re-order tests: sanity -> unit -> integration

    def pytest_runtestloop(self, session: Session) -> Optional[object]:  # pylint: disable=unused-argument
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
            check.conclusion.value = ""
            check.created_at.value = Timestamp().to_string()
        else:
            check = self.client.create(
                kind=InfrahubKind.STANDARDCHECK,
                data={
                    "name": item.name,
                    "origin": self.repository.id,
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
