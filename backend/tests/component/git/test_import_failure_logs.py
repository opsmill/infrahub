from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import (
    CoreCheckDefinition,
    CoreGenericRepository,
    CoreReadOnlyRepository,
    CoreRepository,
    CoreTransformJinja2,
    CoreTransformPython,
)
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.git.import_errors import RepositoryImportError
from infrahub.git.models import GitRepositoryAddReadOnly, GitRepositoryPullReadOnly
from infrahub.git.sync import RepositoryBranchesFailedError
from infrahub.git.tasks import (
    add_git_repository_read_only,
    bootstrap_local_repository,
    pull_read_only,
    sync_repository_from_origin,
)
from infrahub.log import PREFECT_RUN_LOGGERS
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.workers.dependencies import build_event_service
from tests.adapters.event import FailingInfrahubEvent
from tests.helpers.dependency_override import override_dependency
from tests.helpers.flow import call_in_flow
from tests.helpers.git import LocalRemote
from tests.helpers.log import traceback_suppression
from tests.helpers.repository_sync import (
    FLOW_RUN_LOGGER,
    INVALID_YAML_CONFIG,
    create_repository_node,
    flow_run_id_of,
    invalid_yaml_config_message,
    run_add_flow,
    run_flow_for_state,
    run_sync_flow,
)
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import State

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

TRUNK = "main"
INVALID_SCHEMA_CONFIG = "schemas:\n  - schema.yml\n"
INVALID_SCHEMA = 'version: "1.0"\nnodes:\n  - name: x\n'
BROKEN_TRANSFORM_CONFIG = "python_transforms:\n  - name: broken\n    file_path: transform.py\n    class_name: Broken\n"
BROKEN_TRANSFORM_MODULE = 'raise RuntimeError("transform module failed to load")\n'
FINISHED_FAILED_PREFIX = "Finished in state Failed("
INTERFACES_TRANSFORM_CONFIG = (
    "python_transforms:\n  - name: interfaces\n    file_path: transform.py\n    class_name: Interfaces\n"
)
TRANSFORM_WITH_UNKNOWN_QUERY = (
    "from infrahub_sdk.transforms import InfrahubTransform\n\n\n"
    "class Interfaces(InfrahubTransform):\n"
    '    query = "device_inventry"\n\n'
    "    async def transform(self, data):\n"
    "        return data\n"
)
TRANSFORM_WITH_OTHER_CLASS = (
    "from infrahub_sdk.transforms import InfrahubTransform\n\n\n"
    "class Devices(InfrahubTransform):\n"
    '    query = "device_inventory"\n\n'
    "    async def transform(self, data):\n"
    "        return data\n"
)


INVENTORY_QUERY_CONFIG = "queries:\n  - name: device_inventory\n    file_path: inventory.gql\n"
INVENTORY_QUERY = (
    "query device_inventory {\n  CoreRepository {\n    edges {\n      node {\n        id\n      }\n    }\n  }\n}\n"
)
REPORT_TRANSFORM_CONFIG = (
    "jinja2_transforms:\n  - name: report\n    query: device_inventory\n    template_path: {template_path}\n"
)
INVENTORY_CHECK_CONFIG = "check_definitions:\n  - name: inventory\n    file_path: check.py\n    class_name: Inventory\n"
INVENTORY_TRANSFORM_CONFIG = (
    "python_transforms:\n  - name: inventory\n    file_path: transform.py\n    class_name: Inventory\n"
)
INVENTORY_CHECK = (
    "from infrahub_sdk.checks import InfrahubCheck\n\n\n"
    "class {class_name}(InfrahubCheck):\n"
    '    query = "device_inventory"\n\n'
    "    def validate(self, data):\n"
    "        pass\n"
)
INVENTORY_TRANSFORM = (
    "from infrahub_sdk.transforms import InfrahubTransform\n\n\n"
    "class {class_name}(InfrahubTransform):\n"
    '    query = "device_inventory"\n\n'
    "    async def transform(self, data):\n"
    "        return data\n"
)


def report_transform_config(template_path: str) -> str:
    return REPORT_TRANSFORM_CONFIG.format(template_path=template_path)


@dataclass
class EntryFailureCase:
    name: str
    files: dict[str, str]
    expected_reason: str


ENTRY_FAILURE_CASES: list[EntryFailureCase] = [
    EntryFailureCase(
        name="schema_path_missing",
        files={".infrahub.yml": "schemas:\n  - schemas/devices.yml\n"},
        expected_reason="Schema 'schemas/devices.yml': The path does not exist",
    ),
    EntryFailureCase(
        name="schema_directory_without_schema_file",
        files={".infrahub.yml": "schemas:\n  - schemas\n", "schemas/README.md": "Schemas live here.\n"},
        expected_reason="Schema 'schemas': The directory contains no .yml, .yaml or .json file",
    ),
    EntryFailureCase(
        name="schema_file_invalid_yaml",
        files={".infrahub.yml": INVALID_SCHEMA_CONFIG, "schema.yml": "nodes: [\n"},
        expected_reason="Unable to load the file schema.yml, Invalid YAML/JSON file",
    ),
    EntryFailureCase(
        name="schema_file_empty",
        files={".infrahub.yml": INVALID_SCHEMA_CONFIG, "schema.yml": ""},
        expected_reason="Unable to load the file schema.yml, Empty YAML/JSON file",
    ),
    EntryFailureCase(
        name="jinja2_template_missing",
        files={".infrahub.yml": report_transform_config("report.j2")},
        expected_reason="Jinja2 transform 'report' (report.j2): The template file does not exist",
    ),
    EntryFailureCase(
        name="jinja2_template_empty",
        files={".infrahub.yml": report_transform_config("report.j2"), "report.j2": "\n"},
        expected_reason="Jinja2 transform 'report' (report.j2): The template file is empty",
    ),
    EntryFailureCase(
        name="jinja2_template_syntax_error",
        files={".infrahub.yml": report_transform_config("report.j2"), "report.j2": "{{ name }\n"},
        expected_reason="Jinja2 transform 'report' (report.j2): Syntax error in report.j2, line 1: unexpected '}'",
    ),
    EntryFailureCase(
        name="jinja2_template_outside_the_repository",
        files={".infrahub.yml": report_transform_config("../report.j2")},
        expected_reason="Jinja2 transform 'report' (../report.j2): The template path is outside the repository",
    ),
    EntryFailureCase(
        name="check_class_missing",
        files={".infrahub.yml": INVENTORY_CHECK_CONFIG, "check.py": INVENTORY_CHECK.format(class_name="Devices")},
        expected_reason=(
            "Check definition 'inventory' (check.py): The specified class Inventory was not found within the module"
        ),
    ),
]


def invalid_schema_message(branch_name: str) -> str:
    return (
        f"Failed to import branch '{branch_name}': Schema not valid, found '2' error(s) in schema.yml : "
        "nodes[0].name: String should have at least 2 characters (received: 'x'); nodes[0].namespace: Field required"
    )


def run_log_errors(caplog: pytest.LogCaptureFixture, state: State) -> list[logging.LogRecord]:
    """Return the error-level entries the flow run wrote to its task log, in order."""
    flow_run_id = str(flow_run_id_of(state))
    return [
        record
        for record in caplog.records
        if record.name == FLOW_RUN_LOGGER
        and record.levelno >= logging.ERROR
        and vars(record).get("flow_run_id") == flow_run_id
    ]


def records_with_traceback(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name in PREFECT_RUN_LOGGERS and record.exc_info]


async def sync_status(client: InfrahubClient, repository_id: str, branch_name: str) -> str | None:
    repository = await client.get(kind=CoreGenericRepository, id=repository_id, branch=branch_name)
    return repository.sync_status.value


class TestImportFailureLogs(TestInfrahubApp):
    """A failed branch import is logged once, without a Prefect traceback, and stays on its branch."""

    @pytest.fixture(autouse=True)
    def traceback_suppression_installed(self) -> Generator[None, None, None]:
        with traceback_suppression():
            yield

    @pytest.fixture(autouse=True)
    def no_import_sync_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every remote branch is a candidate for import, whatever the environment configures."""
        monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])

    @pytest.fixture(autouse=True)
    def capture_run_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        for logger_name in PREFECT_RUN_LOGGERS:
            caplog.set_level(logging.INFO, logger=logger_name)

    async def _connect(
        self, db: InfrahubDatabase, tmp_path: Path, name: str, branches: list[str] | None = None
    ) -> tuple[LocalRemote, Node]:
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=branches or [])
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        return remote, node

    async def test_expected_failure_is_logged_once_without_traceback(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "invalid-schema-repo"
        branch_name = "invalid-schema"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(
            branch_name=branch_name, files={".infrahub.yml": INVALID_SCHEMA_CONFIG, "schema.yml": INVALID_SCHEMA}
        )
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        assert isinstance(await state.aresult(raise_on_failure=False), RepositoryBranchesFailedError)
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        # Prefect's own closing entry is matched by its prefix, which is the part of its wording it owns.
        import_entry, finished_entry = [record.getMessage() for record in run_log_errors(caplog, state)]
        assert import_entry == invalid_schema_message(branch_name)
        assert finished_entry.startswith(FINISHED_FAILED_PREFIX)
        assert records_with_traceback(caplog) == []

    async def test_unrecognised_failure_is_logged_once_with_its_traceback(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "broken-transform-repo"
        branch_name = "broken-transform"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(
            branch_name=branch_name,
            files={".infrahub.yml": BROKEN_TRANSFORM_CONFIG, "transform.py": BROKEN_TRANSFORM_MODULE},
        )
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        tracebacks = records_with_traceback(caplog)
        assert [(record.getMessage(), type(record.exc_info[1])) for record in tracebacks if record.exc_info] == [
            (
                f"Failed to import branch '{branch_name}': Python transform 'broken' (transform.py): "
                "RuntimeError: transform module failed to load",
                RuntimeError,
            )
        ]

    @pytest.mark.parametrize(
        ("module", "expected_reason"),
        [
            pytest.param(
                TRANSFORM_WITH_UNKNOWN_QUERY, "GraphQL query 'device_inventry' was not found", id="unknown_query"
            ),
            pytest.param(
                TRANSFORM_WITH_OTHER_CLASS,
                "The specified class Interfaces was not found within the module",
                id="unknown_class",
            ),
        ],
    )
    async def test_python_transform_reference_error_names_the_entry(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
        module: str,
        expected_reason: str,
    ) -> None:
        name = f"transform-reference-repo-{len(expected_reason)}"
        branch_name = f"transform-reference-{len(expected_reason)}"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(
            branch_name=branch_name, files={".infrahub.yml": INTERFACES_TRANSFORM_CONFIG, "transform.py": module}
        )
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        import_entry, _ = run_log_errors(caplog, state)
        assert import_entry.getMessage() == (
            f"Failed to import branch '{branch_name}': Python transform 'interfaces' (transform.py): {expected_reason}"
        )
        assert {key: vars(import_entry)[key] for key in ("repository", "branch", "step", "reason")} == {
            "repository": name,
            "branch": branch_name,
            "step": "import",
            "reason": f"Python transform 'interfaces' (transform.py): {expected_reason}",
        }
        assert records_with_traceback(caplog) == []

    async def test_syntax_error_names_the_file_relative_to_the_repository(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "syntax-error-transform-repo"
        branch_name = "syntax-error-transform"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(
            branch_name=branch_name,
            files={".infrahub.yml": BROKEN_TRANSFORM_CONFIG, "transform.py": "x = = 1\n"},
        )
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        import_entry, _ = [record.getMessage() for record in run_log_errors(caplog, state)]
        assert import_entry == (
            f"Failed to import branch '{branch_name}': Python transform 'broken' (transform.py): "
            "Syntax error in transform.py, line 1: invalid syntax"
        )
        assert records_with_traceback(caplog) == []

    async def test_missing_object_file_names_the_file_relative_to_the_repository(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "missing-object-file-repo"
        branch_name = "missing-object-file"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(branch_name=branch_name, files={".infrahub.yml": "objects:\n  - devices.yml\n"})
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        import_entry, _ = [record.getMessage() for record in run_log_errors(caplog, state)]
        assert import_entry == f"Failed to import branch '{branch_name}': File 'devices.yml': The file does not exist"
        assert records_with_traceback(caplog) == []

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ENTRY_FAILURE_CASES])
    async def test_invalid_entry_fails_the_import_and_names_the_entry(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
        test_case: EntryFailureCase,
    ) -> None:
        name = f"{test_case.name.replace('_', '-')}-repo"
        branch_name = test_case.name.replace("_", "-")
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(branch_name=branch_name, files=test_case.files)
        caplog.clear()

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        import_entry, _ = [record.getMessage() for record in run_log_errors(caplog, state)]
        assert import_entry == f"Failed to import branch '{branch_name}': {test_case.expected_reason}"
        assert records_with_traceback(caplog) == []

    async def _import_then_break(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
        name: str,
        valid_files: dict[str, str],
        broken_files: dict[str, str],
    ) -> str:
        """Import a valid commit on a new branch, then sync a commit that breaks it; return the branch name."""
        branch_name = f"{name}-branch"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name=branch_name, db=db)
        remote.commit(branch_name=branch_name, files=valid_files)
        imported = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))
        assert imported.is_completed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.IN_SYNC.value

        remote.commit(branch_name=branch_name, files=broken_files)
        failed = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert failed.is_failed()
        assert await sync_status(client, node.id, branch_name) == RepositorySyncStatus.ERROR_IMPORT.value
        return branch_name

    async def test_failed_import_keeps_the_jinja2_transform(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        branch_name = await self._import_then_break(
            db=db,
            client=client,
            tmp_path=tmp_path,
            name="kept-jinja2-transform-repo",
            valid_files={
                ".infrahub.yml": INVENTORY_QUERY_CONFIG + report_transform_config("report.j2"),
                "inventory.gql": INVENTORY_QUERY,
                "report.j2": "{{ data }}\n",
            },
            broken_files={".infrahub.yml": INVENTORY_QUERY_CONFIG + report_transform_config("missing.j2")},
        )

        transform = await client.get(kind=CoreTransformJinja2, name__value="report", branch=branch_name)
        assert (
            transform.template_path.value,
            transform.dependencies.value,
            transform.dependencies_complete.value,
        ) == ("report.j2", ["report.j2"], True)

    async def test_failed_import_keeps_the_check_definition(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        branch_name = await self._import_then_break(
            db=db,
            client=client,
            tmp_path=tmp_path,
            name="kept-check-definition-repo",
            valid_files={
                ".infrahub.yml": INVENTORY_QUERY_CONFIG + INVENTORY_CHECK_CONFIG,
                "inventory.gql": INVENTORY_QUERY,
                "check.py": INVENTORY_CHECK.format(class_name="Inventory"),
            },
            broken_files={"check.py": INVENTORY_CHECK.format(class_name="Devices")},
        )

        check = await client.get(kind=CoreCheckDefinition, name__value="inventory", branch=branch_name)
        assert (check.file_path.value, check.class_name.value) == ("check.py", "Inventory")

    async def test_failed_import_keeps_the_python_transform(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        branch_name = await self._import_then_break(
            db=db,
            client=client,
            tmp_path=tmp_path,
            name="kept-python-transform-repo",
            valid_files={
                ".infrahub.yml": INVENTORY_QUERY_CONFIG + INVENTORY_TRANSFORM_CONFIG,
                "inventory.gql": INVENTORY_QUERY,
                "transform.py": INVENTORY_TRANSFORM.format(class_name="Inventory"),
            },
            broken_files={"transform.py": INVENTORY_TRANSFORM.format(class_name="Devices")},
        )

        transform = await client.get(kind=CoreTransformPython, name__value="inventory", branch=branch_name)
        assert (transform.file_path.value, transform.class_name.value) == ("transform.py", "Inventory")

    async def test_failure_after_the_import_steps_stays_on_its_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A failed commit event is recorded on each branch in turn, which keeps its imported objects in sync."""
        name = "failing-commit-event-repo"
        branches = ["event-first", "event-second"]
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        for branch_name in branches:
            await create_branch(branch_name=branch_name, db=db)
            remote.commit(branch_name=branch_name, files={"data.txt": f"{branch_name}\n"})
        failing = FailingInfrahubEvent(failing_kind=CommitUpdatedEvent)
        caplog.clear()

        with override_dependency(build_event_service, lambda: failing, dependency_provider=dependency_provider):
            state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryBranchesFailedError)
        assert sorted(error.outcome.report.failed_import_branches) == branches
        statuses = {branch_name: await sync_status(client, node.id, branch_name) for branch_name in branches}
        assert statuses == dict.fromkeys(branches, RepositorySyncStatus.IN_SYNC.value)
        assert sorted(
            (record.getMessage(), type(record.exc_info[1]))
            for record in records_with_traceback(caplog)
            if record.exc_info
        ) == [
            (f"Failed to import branch '{branch_name}': RuntimeError: CommitUpdatedEvent rejected", RuntimeError)
            for branch_name in branches
        ]

    async def test_add_flow_syncs_other_branches_when_the_default_branch_import_fails(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "broken-default-branch-repo"
        other_branch = "feature-valid"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[other_branch])
        remote.commit(branch_name=TRUNK, files={".infrahub.yml": INVALID_YAML_CONFIG})
        await create_branch(branch_name=other_branch, db=db)
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        bus_simulator.messages.clear()
        caplog.clear()

        state = await run_add_flow(node=node, name=name, location=str(remote.directory))

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryImportError)
        assert error.message == invalid_yaml_config_message(name)
        assert await sync_status(client, node.id, TRUNK) == RepositorySyncStatus.ERROR_IMPORT.value
        assert await sync_status(client, node.id, other_branch) == RepositorySyncStatus.IN_SYNC.value
        assert [
            message.repository_id for message in bus_simulator.messages if isinstance(message, RefreshGitFetch)
        ] == [node.id]
        assert records_with_traceback(caplog) == []

    async def test_scheduled_sync_of_a_new_clone_syncs_other_branches_when_the_default_branch_import_fails(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "broken-default-on-new-clone-repo"
        other_branch = "feature-on-new-clone"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[other_branch])
        remote.commit(branch_name=TRUNK, files={".infrahub.yml": INVALID_YAML_CONFIG})
        await create_branch(branch_name=other_branch, db=db)
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        repository = await client.get(kind=CoreRepository, id=node.id)

        repo = await call_in_flow(
            lambda: bootstrap_local_repository(
                repo_name=name, repository=repository, infrahub_branch=registry.default_branch, client=client
            )
        )
        assert repo is not None
        await call_in_flow(
            lambda: sync_repository_from_origin(
                repository=repository,
                repo=repo,
                staging_branch=None,
                infrahub_branch=registry.default_branch,
                default_branch_id=str(UUIDT()),
                client=client,
            )
        )

        assert await sync_status(client, node.id, TRUNK) == RepositorySyncStatus.ERROR_IMPORT.value
        assert await sync_status(client, node.id, other_branch) == RepositorySyncStatus.IN_SYNC.value

    async def test_read_only_import_failure_keeps_the_previous_commit(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "read-only-repo"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        node = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await node.new(db=db, name=name, location=str(remote.directory), ref=TRUNK)
        await node.save(db=db)
        added = await run_flow_for_state(
            add_git_repository_read_only,
            parameters={
                "model": GitRepositoryAddReadOnly(
                    location=str(remote.directory),
                    repository_id=node.id,
                    repository_name=name,
                    ref=TRUNK,
                    infrahub_branch_name=registry.default_branch,
                    infrahub_branch_id=str(UUIDT()),
                    internal_status=RepositoryInternalStatus.ACTIVE.value,
                )
            },
        )
        assert added.is_completed()
        imported_commit = (await client.get(kind=CoreReadOnlyRepository, id=node.id)).commit.value
        remote.commit(branch_name=TRUNK, files={".infrahub.yml": INVALID_YAML_CONFIG})
        caplog.clear()

        state = await run_flow_for_state(
            pull_read_only,
            parameters={
                "model": GitRepositoryPullReadOnly(
                    location=str(remote.directory),
                    repository_id=node.id,
                    repository_name=name,
                    ref=TRUNK,
                    infrahub_branch_name=registry.default_branch,
                    infrahub_branch_id=str(UUIDT()),
                )
            },
        )

        assert state.is_failed()
        assert isinstance(await state.aresult(raise_on_failure=False), RepositoryImportError)
        repository = await client.get(kind=CoreReadOnlyRepository, id=node.id)
        assert repository.sync_status.value == RepositorySyncStatus.ERROR_IMPORT.value
        assert repository.commit.value == imported_commit
        assert records_with_traceback(caplog) == []
