import pytest
from infrahub_sdk.client import Config as InfrahubClientConfig
from infrahub_sdk.client import InfrahubClientSync
from infrahub_sdk.node import InfrahubNodeSync

from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp

OUTCOME_TO_CONCLUSION_MAP = {"passed": "success", "failed": "failure", "skipped": "failure"}
OUTCOME_TO_SEVERITY_MAP = {"passed": "success", "failed": "error", "skipped": "warning"}
ORDER_TYPE_MAP = {"infrahub_smoke": 0, "infrahub_unit": 1, "infrahub_integration": 2}
ORDER_ITEM_MAP = {
    "infrahub_check": 0,
    "infrahub_graphql_query": 1,
    "infrahub_jinja2_transform": 2,
    "infrahub_python_transform": 3,
}


class InfrahubBackendPlugin:
    def __init__(self, config: InfrahubClientConfig, repository_id: str, proposed_change_id: str) -> None:
        self.client = InfrahubClientSync(config=config)

        self.repository_id = repository_id
        self.proposed_change_id = proposed_change_id

        self.proposed_change: InfrahubNodeSync
        self.validator: InfrahubNodeSync
        self.checks: dict[str, InfrahubNodeSync] = {}

    def get_repository_validator(self) -> tuple[InfrahubNodeSync, bool]:
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

    def pytest_collection_modifyitems(
        self,
        session: pytest.Session,  # noqa: ARG002
        config: pytest.Config,  # noqa: ARG002
        items: list[pytest.Item],
    ) -> None:
        """This function is called after item collection and gives the opportunity to work on the collection before sending the items for testing.

        All items without an "infrahub" marker will be discarded. Items will also be re-ordered to be run in a specific order:
        1. Smoke tests
        2. Unit tests
        3. Integration tests

        TODO: this function should also filter items that do not need to run
        """
        filtered_items = [i for i in items if i.get_closest_marker("infrahub")]

        def sort_key(item: pytest.Item) -> tuple[int, int]:
            type_cost = 99
            for marker_name, priority in ORDER_TYPE_MAP.items():
                if item.get_closest_marker(marker_name):
                    type_cost = priority
                    break

            item_cost = 99
            for marker_name, priority in ORDER_ITEM_MAP.items():
                if item.get_closest_marker(marker_name):
                    type_cost = priority
                    break

            return type_cost, item_cost

        filtered_items.sort(key=sort_key)
        items[:] = filtered_items

    def pytest_collection_finish(self, session: pytest.Session) -> None:  # noqa: ARG002
        """This function is called when tests have been collected and modified, meaning they are ready to be run."""
        self.proposed_change = self.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=self.proposed_change_id)
        self.proposed_change.validations.fetch()

        self.validator, is_new_validator = self.get_repository_validator()
        # Workaround for https://github.com/opsmill/infrahub/issues/2184
        if not is_new_validator:
            self.validator.checks.fetch()
            for relationship in self.validator.checks.peers:
                check = relationship.peer
                self.checks[check.origin.value] = check

    def pytest_runtestloop(self, session: pytest.Session) -> object | None:  # noqa: ARG002
        """This function is called when the test loop is being run."""
        self.validator.conclusion.value = "unknown"
        self.validator.state.value = "in_progress"
        self.validator.started_at.value = Timestamp().to_string()
        self.validator.completed_at.value = ""

        return None

    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        """Create a StandardCheck for each test item to later record its details.

        If a check already exists, reset it to its default values.
        """
        created_at = Timestamp().to_string()
        check = self.checks.get(item.nodeid, None)
        if check:
            check.message.value = ""
            check.conclusion.value = "unknown"
            check.severity.value = "info"
            check.created_at.value = created_at
        else:
            check = self.client.create(
                kind=InfrahubKind.STANDARDCHECK,
                data={
                    "name": item.name,
                    "origin": item.nodeid,
                    "kind": "TestReport",
                    "validator": self.validator.id,
                    "created_at": created_at,
                    "severity": "info",
                },
            )
            self.checks[item.nodeid] = check

        check.save()

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """This function is called 3 times per test: setup, call, teardown."""
        if report.when != "call":
            return

        check = self.checks[report.nodeid]
        check.message.value = report.longreprtext
        check.severity.value = OUTCOME_TO_SEVERITY_MAP[report.outcome]
        check.conclusion.value = OUTCOME_TO_CONCLUSION_MAP[report.outcome]
        # Workaround for https://github.com/opsmill/infrahub/issues/2184
        check.update(do_full_update=True)

    def pytest_sessionfinish(self, session: pytest.Session) -> None:  # noqa: ARG002
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
