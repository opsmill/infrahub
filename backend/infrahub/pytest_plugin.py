from typing import TYPE_CHECKING, Dict, List, Optional

from infrahub_sdk.client import Config as InfrahubClientConfig
from infrahub_sdk.client import InfrahubClientSync
from pytest import Config, Item, Session, TestReport

from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNodeSync


OUTCOME_TO_CONCLUSION_MAP = {"passed": "success", "failed": "failure", "skipped": "unknown"}


class InfrahubBackendPlugin:
    def __init__(self, config: InfrahubClientConfig, repository_id: str, proposed_change_id: str) -> None:
        self.client = InfrahubClientSync(config=config)

        self.repository = self.client.get(kind=InfrahubKind.GENERICREPOSITORY, id=repository_id)
        self.proposed_change = self.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=proposed_change_id)

        self.validator: InfrahubNodeSync
        self.checks: Dict[str, InfrahubNodeSync] = {}

    def set_repository_validator(self) -> None:
        self.proposed_change.validations.fetch()

        validator_name = f"Repository Tests Validator: {self.repository.name.value}"
        for relationship in self.proposed_change.validations.peers:
            existing_validator = relationship.peer

            if (
                existing_validator.typename == InfrahubKind.REPOSITORYVALIDATOR
                and existing_validator.repository.id == self.repository.id
                and existing_validator.label.value == validator_name
            ):
                self.validator = existing_validator

        if not self.validator:
            self.validator = self.client.create(
                kind=InfrahubKind.REPOSITORYVALIDATOR,
                data={"label": validator_name, "proposed_change": self.proposed_change, "repository": self.repository},
            )

        self.validator.save()

    def pytest_sessionstart(self, session: Session) -> None:  # pylint: disable=unused-argument
        """Function running at the very start of the test session"""

    def pytest_sessionfinish(self, session: Session) -> None:  # pylint: disable=unused-argument
        conclusion = "success"

        for check in self.checks.values():
            if check.conclusion.value != "success":
                conclusion = check.conclusion.value
                break

        self.validator.state.value = "completed"
        self.validator.completed_at.value = Timestamp().to_string()
        self.validator.conclusion.value = conclusion
        self.validator.save()

    def pytest_collection_modifyitems(self, session: Session, config: Config, items: List[Item]) -> None:  # pylint: disable=unused-argument
        self.set_repository_validator()
        # TODO: Filter tests according to what's been requested
        # TODO: Re-order tests: sanity -> unit -> integration

    def pytest_runtestloop(self, session: Session) -> Optional[object]:  # pylint: disable=unused-argument
        self.validator.conclusion.value = "unknown"
        self.validator.state.value = "in_progress"
        self.validator.started_at.value = Timestamp().to_string()
        self.validator.completed_at.value = ""

        return None

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """This function is called 3 times per test: setup, call, teardown."""
        # TODO: Override checks if they already exist
        if report.when == "setup":
            check = self.client.create(
                kind=InfrahubKind.STANDARDCHECK,
                data={
                    "name": report.head_line,
                    "origin": self.repository.id,
                    "kind": "TestReport",
                    "validator": self.validator.id,
                    "created_at": Timestamp().to_string(),
                    "severity": "info",
                    "conclusion": OUTCOME_TO_CONCLUSION_MAP[report.outcome],
                },
            )
            check.save()
            self.checks[report.nodeid] = check
        else:
            check = self.checks[report.nodeid]
            if check.conclusion.value == "success" and report.outcome != "passed":
                check.conclusion.value = OUTCOME_TO_CONCLUSION_MAP[report.outcome]
            check.save()
