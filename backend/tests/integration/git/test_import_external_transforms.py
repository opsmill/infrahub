from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from infrahub_sdk.protocols import (
    CoreArtifactDefinition,
    CoreGraphQLQuery,
    CoreReadOnlyRepository,
    CoreTransformExternal,
)

from infrahub.core.constants import InfrahubKind, RepositorySyncStatus
from infrahub.core.node import Node
from infrahub.git.models import GitReadOnlyRepositoryImportCommit
from infrahub.workflows.catalogue import GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

REPOSITORY_NAME = "external-transforms"
PEOPLE_QUERY = """
query people_report($name: String!) {
  TestingPerson(name__value: $name) {
    edges {
      node {
        name {
          value
        }
      }
    }
  }
}
"""
QUERIES = [{"name": "people_report", "file_path": "queries/people_report.gql"}]
ARTIFACT_DEFINITION = {
    "name": "people config",
    "artifact_name": "people-config",
    "parameters": {"name": "name__value"},
    "content_type": "text/plain",
    # An empty target group keeps the import from rendering any artifact.
    "targets": "nobody",
    "transformation": "people_external",
}


def _external_transform(version: str, timeout: int = 600) -> dict[str, Any]:
    return {
        "name": "people_external",
        "query": "people_report",
        "version": version,
        "description": "Rendered by an external engine",
        "timeout": timeout,
    }


def _commit_config(file_repo: FileRepo, config: dict[str, Any]) -> str:
    (Path(file_repo.path) / ".infrahub.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    file_repo.repo.git.add(".")
    return file_repo.repo.index.commit("update repository config").hexsha


class TestImportExternalTransforms(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def file_repo(self, git_repos_source_dir_module_scope: Path) -> FileRepo:
        file_repo = FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        query_path = Path(file_repo.path) / "queries" / "people_report.gql"
        query_path.parent.mkdir(parents=True, exist_ok=True)
        query_path.write_text(PEOPLE_QUERY, encoding="utf-8")
        _commit_config(file_repo=file_repo, config={"queries": QUERIES})
        return file_repo

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        nobody = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await nobody.new(db=db, name="nobody")
        await nobody.save(db=db)

    @pytest.fixture(scope="class")
    async def repository_id(self, initial_dataset: None, file_repo: FileRepo, client: InfrahubClient) -> str:
        repository = await client.create(
            kind=CoreReadOnlyRepository, name=REPOSITORY_NAME, location=file_repo.path, ref="main"
        )
        await repository.save()
        return repository.id

    async def _commit_and_sync(
        self,
        client: InfrahubClient,
        service: InfrahubServices,
        repository_id: str,
        file_repo: FileRepo,
        config: dict[str, Any],
    ) -> None:
        commit = _commit_config(file_repo=file_repo, config=config)
        await service.workflow.execute_workflow(
            workflow=GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
            parameters={
                "model": GitReadOnlyRepositoryImportCommit(
                    repository_id=repository_id,
                    repository_name=REPOSITORY_NAME,
                    repository_kind=InfrahubKind.READONLYREPOSITORY,
                    infrahub_branch_name="main",
                    ref="main",
                )
            },
        )
        repository = await client.get(kind=CoreReadOnlyRepository, id=repository_id)
        assert repository.commit.value == commit
        assert repository.sync_status.value == RepositorySyncStatus.IN_SYNC.value

    async def test_create_update_and_delete(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": QUERIES,
                "external_transforms": [_external_transform(version="1.0", timeout=300)],
                "artifact_definitions": [ARTIFACT_DEFINITION],
            },
        )
        query = await client.get(kind=CoreGraphQLQuery, name__value="people_report")
        transform = await client.get(kind=CoreTransformExternal, name__value="people_external")
        artifact_definition = await client.get(kind=CoreArtifactDefinition, name__value="people config")
        assert transform.query.id == query.id
        assert transform.repository.id == repository_id
        assert transform.version.value == "1.0"
        assert transform.timeout.value == 300
        assert transform.description.value == "Rendered by an external engine"
        assert transform.dependencies.value == []
        assert transform.dependencies_complete.value is True
        assert artifact_definition.transformation.id == transform.id
        first_fingerprint = transform.fingerprint.value
        assert first_fingerprint

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": QUERIES,
                "external_transforms": [_external_transform(version="1.1")],
                "artifact_definitions": [ARTIFACT_DEFINITION],
            },
        )
        updated = await client.get(kind=CoreTransformExternal, id=transform.id)
        assert updated.version.value == "1.1"
        assert updated.timeout.value == 600
        assert updated.fingerprint.value != first_fingerprint

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={"queries": QUERIES},
        )
        assert await client.filters(kind=CoreTransformExternal, ids=[transform.id]) == []
        assert await client.filters(kind=CoreArtifactDefinition, ids=[artifact_definition.id]) == []
