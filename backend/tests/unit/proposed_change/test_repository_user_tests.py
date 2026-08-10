from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from infrahub_sdk.client import Config as InfrahubClientConfig

from infrahub.core.constants import InfrahubKind
from infrahub.proposed_change.tasks import _run_repository_tests
from infrahub.pytest_plugin import SESSION_CHECK_ORIGIN, InfrahubBackendPlugin

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ADDRESS = "http://localhost:8000"

REPOSITORY_CONFIG = """---
jinja2_transforms:
  - name: my_transform
    query: my_query
    template_path: templates/my_template.j2
"""

PASSING_INFRAHUB_TEST = """---
infrahub_tests:
  - resource: Jinja2Transform
    resource_name: my_transform
    tests:
      - name: smoke_test
        spec:
          kind: jinja2-transform-smoke
"""

# `resource` is not a value the loader knows, so building the test file model raises during collect().
MALFORMED_INFRAHUB_TEST = """---
infrahub_tests:
  - resource: NotAResourceKind
    resource_name: my_transform
    tests:
      - name: smoke_test
        spec:
          kind: jinja2-transform-smoke
"""

BROKEN_PYTHON_TEST = """import a_module_that_does_not_exist  # noqa: F401


def test_something_the_user_cares_about() -> None:
    assert True
"""

BROKEN_CONFTEST = "import a_module_that_does_not_exist  # noqa: F401\n"


# Fields the plugin reads back as `node.<field>.id` rather than `node.<field>.value`.
RELATIONSHIP_FIELDS = {"repository", "proposed_change", "validator"}


@dataclass
class FakeAttribute:
    value: Any = None


@dataclass
class FakeReference:
    id: str


@dataclass
class FakePeer:
    peer: FakeNode


class FakeRelationship:
    def __init__(self) -> None:
        self.peers: list[FakePeer] = []

    def fetch(self) -> None:
        return None


class FakeNode:
    """Stands in for InfrahubNodeSync, whose fields are read and written as `node.<field>.value`."""

    def __init__(
        self,
        node_id: str,
        typename: str,
        data: dict[str, Any] | None = None,
        relationships: tuple[str, ...] = (),
    ) -> None:
        self.id = node_id
        self.typename = typename
        self.save_count = 0

        fields: dict[str, Any] = {name: FakeRelationship() for name in relationships}
        for name, value in (data or {}).items():
            fields[name] = (
                FakeReference(id=value if isinstance(value, str) else value.id)
                if name in RELATIONSHIP_FIELDS
                else FakeAttribute(value)
            )
        self._fields = fields

    def __getattr__(self, name: str) -> Any:
        fields = self.__dict__["_fields"]
        if name not in fields:
            fields[name] = FakeAttribute()
        return fields[name]

    def save(self) -> None:
        self.save_count += 1

    def update(self, do_full_update: bool = False) -> None:
        self.save_count += 1


class FakeClient:
    """Stands in for the Infrahub instance, keeping what the plugin writes so a re-run can find it."""

    def __init__(self) -> None:
        self.config = InfrahubClientConfig(address=ADDRESS)
        self.proposed_change = FakeNode(node_id="pc-1", typename="CoreProposedChange", relationships=("validations",))
        self.nodes: list[FakeNode] = []

    def get(self, kind: str, id: str, **kwargs: Any) -> FakeNode:
        return self.proposed_change

    def create(self, kind: str, data: dict[str, Any]) -> FakeNode:
        node = FakeNode(node_id=f"{kind}-{len(self.nodes)}", typename=kind, data=data, relationships=("checks",))
        self.nodes.append(node)

        if kind == InfrahubKind.REPOSITORYVALIDATOR:
            self.proposed_change.validations.peers.append(FakePeer(peer=node))
        elif kind == InfrahubKind.STANDARDCHECK:
            for candidate in self.nodes:
                if candidate.id == data["validator"]:
                    candidate.checks.peers.append(FakePeer(peer=node))

        return node

    def session_checks(self) -> list[FakeNode]:
        return [node for node in self.nodes if node.origin.value == SESSION_CHECK_ORIGIN]


@dataclass
class Repository:
    directory: Path
    config_file: Path
    tests: Path = field(init=False)

    def __post_init__(self) -> None:
        self.tests = self.directory / "tests"


def build_repository(
    root: Path,
    *,
    infrahub_test: str | None = None,
    python_test: str | None = None,
    conftest: str | None = None,
) -> Repository:
    directory = root / "user_repository"
    (directory / "tests").mkdir(parents=True)
    (directory / "templates").mkdir()

    config_file = directory / ".infrahub.yml"
    config_file.write_text(REPOSITORY_CONFIG, encoding="utf-8")
    (directory / "templates" / "my_template.j2").write_text("hello {{ name }}\n", encoding="utf-8")

    if infrahub_test is not None:
        (directory / "tests" / "test_infrahub.yml").write_text(infrahub_test, encoding="utf-8")
    if python_test is not None:
        (directory / "tests" / "test_user_code.py").write_text(python_test, encoding="utf-8")
    if conftest is not None:
        (directory / "tests" / "conftest.py").write_text(conftest, encoding="utf-8")

    return Repository(directory=directory, config_file=config_file)


@dataclass
class SessionResult:
    exit_code: int | pytest.ExitCode
    validator: FakeNode | None
    tests_run: list[str]

    @property
    def conclusion(self) -> str | None:
        return self.validator.conclusion.value if self.validator else None

    @property
    def state(self) -> str | None:
        return self.validator.state.value if self.validator else None


# The session under test runs nested inside this one, so it has to be cut off from the plugins of
# the outer run. A git agent only ever has the SDK plugin loaded, which is what this reproduces.
ISOLATED_SESSION_ENV = {
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTEST_ADDOPTS": "-p infrahub_sdk.pytest_plugin.plugin",
}


def run_repository_tests(
    repository: Repository,
    client: FakeClient | None = None,
    address: str | None = ADDRESS,
) -> SessionResult:
    client = client or FakeClient()
    with (
        patch.dict(os.environ, ISOLATED_SESSION_ENV),
        patch("infrahub.pytest_plugin.InfrahubClientSync", return_value=client),
    ):
        plugin = InfrahubBackendPlugin(
            config=client.config,
            repository_id="repository-1",
            proposed_change_id="pc-1",
        )
        exit_code = _run_repository_tests(
            test_directory=repository.tests,
            config_file=str(repository.config_file),
            address=address,
            plugin=plugin,
        )

    tests_run = [nodeid for nodeid in plugin.checks if "::" in nodeid]
    return SessionResult(
        exit_code=exit_code,
        validator=plugin.validator if plugin.validator_loaded else None,
        tests_run=tests_run,
    )


def test_infrahub_tests_still_run_when_a_user_python_test_cannot_be_imported(tmp_path: Path) -> None:
    """A user's own broken test file must not stop the Infrahub tests from running."""
    repository = build_repository(tmp_path, infrahub_test=PASSING_INFRAHUB_TEST, python_test=BROKEN_PYTHON_TEST)

    result = run_repository_tests(repository)

    assert len(result.tests_run) == 1
    assert result.tests_run[0].endswith("infrahub_jinja2_transform__my_transform__smoke_test")
    assert result.conclusion == "success"


def test_user_python_tests_are_never_executed(tmp_path: Path) -> None:
    """Only Infrahub tests belong to this session, so a user's passing test must not be collected either."""
    passing_python_test = "def test_something_the_user_cares_about() -> None:\n    assert True\n"
    repository = build_repository(tmp_path, infrahub_test=PASSING_INFRAHUB_TEST, python_test=passing_python_test)

    result = run_repository_tests(repository)

    assert not [nodeid for nodeid in result.tests_run if "test_user_code" in nodeid]
    assert len(result.tests_run) == 1


def test_validator_reports_failure_when_a_test_file_cannot_be_collected(tmp_path: Path) -> None:
    """Collection is interrupted, so no test runs — the validator must not claim success."""
    repository = build_repository(tmp_path, infrahub_test=MALFORMED_INFRAHUB_TEST)

    result = run_repository_tests(repository)

    assert result.tests_run == []
    assert result.conclusion == "failure"
    assert result.state == "completed"


def test_validator_reports_failure_when_conftest_cannot_be_imported(tmp_path: Path) -> None:
    """The session gives up before it starts, so the outcome has to be recorded by the caller."""
    repository = build_repository(tmp_path, infrahub_test=PASSING_INFRAHUB_TEST, conftest=BROKEN_CONFTEST)

    result = run_repository_tests(repository)

    assert result.tests_run == []
    assert result.conclusion == "failure"
    assert result.state == "completed"


def test_validator_reports_failure_when_the_session_stops_before_the_tests(tmp_path: Path) -> None:
    """An unusable address makes the SDK plugin bail out with a passing exit code — still no result."""
    repository = build_repository(tmp_path, infrahub_test=PASSING_INFRAHUB_TEST)

    result = run_repository_tests(repository, address=None)

    assert result.tests_run == []
    assert result.conclusion == "failure"
    assert result.state == "completed"


def test_fixing_the_repository_clears_the_reported_session_failure(tmp_path: Path) -> None:
    """The validator is reused across runs, so the failure of an earlier run must not outlive it."""
    client = FakeClient()
    repository = build_repository(tmp_path, infrahub_test=MALFORMED_INFRAHUB_TEST)

    first_run = run_repository_tests(repository, client=client)
    assert first_run.conclusion == "failure"

    (repository.tests / "test_infrahub.yml").write_text(PASSING_INFRAHUB_TEST, encoding="utf-8")
    second_run = run_repository_tests(repository, client=client)

    assert second_run.conclusion == "success"
    assert len(client.session_checks()) == 1
    assert client.session_checks()[0].conclusion.value == "success"


def test_failing_infrahub_test_still_reports_failure(tmp_path: Path) -> None:
    """A test that runs and fails must keep driving the conclusion, not be masked by the exit code."""
    repository = build_repository(tmp_path, infrahub_test=PASSING_INFRAHUB_TEST)
    # The smoke test parses the template, so invalid Jinja2 syntax fails it at call time.
    (repository.directory / "templates" / "my_template.j2").write_text("hello {{ name %}\n", encoding="utf-8")

    result = run_repository_tests(repository)

    assert len(result.tests_run) == 1
    assert result.conclusion == "failure"
    assert result.state == "completed"
