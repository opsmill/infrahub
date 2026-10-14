"""The run that reimporting the objects of a repository commit records in the cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.git.models import GitRepositoryImportObjects
from infrahub.git.tasks import import_objects_from_git_repository
from infrahub.workers.dependencies import build_cache
from tests.adapters.cache import RecordingCache
from tests.helpers.dependency_override import override_dependency
from tests.helpers.git import LocalRemote
from tests.helpers.repository_activity import (
    last_run_branches,
    run_record_operations,
    run_record_writes,
    stored_run_keys,
)
from tests.helpers.repository_sync import (
    INVALID_YAML_CONFIG,
    create_repository_node,
    run_add_flow,
    run_flow_for_state,
)
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import State

    from infrahub.database import InfrahubDatabase


class TestImportObjectsActivity(TestInfrahubApp):
    async def _reimport(
        self, db: InfrahubDatabase, tmp_path: Path, dependency_provider: Provider, name: str, files: dict[str, str]
    ) -> tuple[str, RecordingCache, State]:
        """Add a repository, commit the files on its trunk, and reimport that commit while recording the cache."""
        remote = LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[])
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch="main",
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        added = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert added.is_completed()
        commit = remote.commit(branch_name="main", files=files)
        model = GitRepositoryImportObjects(
            repository_id=node.id,
            repository_name=name,
            repository_kind=InfrahubKind.REPOSITORY,
            commit=commit,
            infrahub_branch_name=registry.default_branch,
        )
        cache = RecordingCache()

        with override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider):
            state = await run_flow_for_state(import_objects_from_git_repository, parameters={"model": model})

        return node.id, cache, state

    async def test_a_reimport_records_its_steps_while_it_runs_and_the_branch_as_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        repository_id, cache, state = await self._reimport(
            db=db,
            tmp_path=tmp_path,
            dependency_provider=dependency_provider,
            name="activity-reimport-repo",
            files={"data.txt": "v2\n"},
        )

        assert state.is_completed()
        assert run_record_operations(cache=cache, repository_id=repository_id) == {"reimport"}
        assert run_record_writes(cache=cache, repository_id=repository_id) == [
            (None, None),
            ("building", registry.default_branch),
            ("applying", registry.default_branch),
        ]
        assert stored_run_keys(cache=cache, repository_id=repository_id) == []
        assert last_run_branches(cache=cache, repository_id=repository_id, operation="reimport") == [
            {"branch_name": registry.default_branch, "outcome": "imported"}
        ]

    async def test_a_reimport_that_fails_records_the_branch_as_failed(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        repository_id, cache, state = await self._reimport(
            db=db,
            tmp_path=tmp_path,
            dependency_provider=dependency_provider,
            name="activity-failed-reimport-repo",
            files={".infrahub.yml": INVALID_YAML_CONFIG},
        )

        assert state.is_failed()
        assert run_record_writes(cache=cache, repository_id=repository_id) == [
            (None, None),
            ("building", registry.default_branch),
        ]
        assert stored_run_keys(cache=cache, repository_id=repository_id) == []
        assert last_run_branches(cache=cache, repository_id=repository_id, operation="reimport") == [
            {"branch_name": registry.default_branch, "outcome": "failed"}
        ]
