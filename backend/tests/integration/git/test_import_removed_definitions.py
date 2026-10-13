from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreGeneratorDefinition,
    CoreGraphQLQuery,
    CoreReadOnlyRepository,
    CoreTransformJinja2,
    CoreTransformPython,
)

from infrahub.core.constants import InfrahubKind, RepositorySyncStatus
from infrahub.core.node import Node
from infrahub.git.models import GitReadOnlyRepositoryImportCommit
from infrahub.workflows.catalogue import GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

REPOSITORY_NAME = "car-dealership"


def _person_query(name: str) -> str:
    return f"""
query {name}($name: String!) {{
  TestingPerson(name__value: $name) {{
    edges {{
      node {{
        name {{
          value
        }}
      }}
    }}
  }}
}}
"""


PEOPLE_REPORT_TRANSFORM = """from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class PeopleReport(InfrahubTransform):
    query = "people_report"

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"people": len(data["TestingPerson"]["edges"])}
"""

PEOPLE_TEMPLATE = "{{ data.TestingPerson.edges | length }}\n"

# Artifacts render against the commit the repository last advanced to, so every file a later
# commit's config references already exists in the base commit, which declares nothing itself.
BASE_FILES: dict[str, str] = {
    **{
        f"queries/{name}.gql": _person_query(name=name)
        for name in ("people_base", "people_report", "people_card", "people_old", "people_new", "people_generator")
    },
    "transforms/people_report.py": PEOPLE_REPORT_TRANSFORM,
    "templates/people.j2": PEOPLE_TEMPLATE,
}


def _query_config(name: str) -> dict[str, str]:
    return {"name": name, "file_path": f"queries/{name}.gql"}


# A query every commit keeps, so a removal commit still declares queries, as a real repository does.
BASE_QUERY = _query_config(name="people_base")
BASE_CONFIG: dict[str, Any] = {"queries": [BASE_QUERY]}


def _jinja2_transform_config(name: str, query: str) -> dict[str, str]:
    return {"name": name, "query": query, "template_path": "templates/people.j2"}


class TestImportRemovedDefinitions(TestInfrahubApp):
    """Removing objects from the repository config deletes them, whatever else in the commit references them."""

    @pytest.fixture(scope="class")
    def file_repo(self, git_repos_source_dir_module_scope: Path) -> FileRepo:
        file_repo = FileRepo(name=REPOSITORY_NAME, sources_directory=git_repos_source_dir_module_scope)
        source = Path(file_repo.path)
        for relative_path, content in BASE_FILES.items():
            target = source / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _commit_config(file_repo=file_repo, config=BASE_CONFIG)
        return file_repo

    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

    @pytest.fixture(scope="class")
    async def repository_id(
        self,
        initial_dataset: None,
        git_repos_dir_module_scope: Path,
        file_repo: FileRepo,
        client: InfrahubClient,
    ) -> str:
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
        """Commit a new repository config, import it, and check the repository advanced to that commit."""
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

    @pytest.fixture(autouse=True)
    async def restore_base_config(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> AsyncGenerator[None, None]:
        yield
        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=BASE_CONFIG
        )

    async def test_remove_artifact_definition_with_its_transform_and_query(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [
                    {
                        "name": "PeopleReport",
                        "class_name": "PeopleReport",
                        "file_path": "transforms/people_report.py",
                    }
                ],
                "artifact_definitions": [
                    {
                        "name": "people report",
                        "artifact_name": "people-report",
                        "parameters": {"name": "name__value"},
                        "content_type": "application/json",
                        "targets": "people",
                        "transformation": "PeopleReport",
                    }
                ],
            },
        )
        query = await client.get(kind=CoreGraphQLQuery, name__value="people_report")
        transform = await client.get(kind=CoreTransformPython, name__value="PeopleReport")
        artifact_definition = await client.get(kind=CoreArtifactDefinition, name__value="people report")
        assert transform.query.id == query.id
        assert artifact_definition.transformation.id == transform.id
        artifacts = await client.filters(kind=CoreArtifact, definition__ids=[artifact_definition.id])
        assert len(artifacts) == 1

        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=BASE_CONFIG
        )

        assert await client.filters(kind=CoreGraphQLQuery, ids=[query.id]) == []
        assert await client.filters(kind=CoreTransformPython, ids=[transform.id]) == []
        assert await client.filters(kind=CoreArtifactDefinition, ids=[artifact_definition.id]) == []
        assert await client.filters(kind=CoreArtifact, ids=[artifacts[0].id]) == []

    async def test_remove_jinja2_transform_with_its_query(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_card")],
                "jinja2_transforms": [_jinja2_transform_config(name="people_card", query="people_card")],
            },
        )
        query = await client.get(kind=CoreGraphQLQuery, name__value="people_card")
        transform = await client.get(kind=CoreTransformJinja2, name__value="people_card")
        assert transform.query.id == query.id

        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=BASE_CONFIG
        )

        assert await client.filters(kind=CoreGraphQLQuery, ids=[query.id]) == []
        assert await client.filters(kind=CoreTransformJinja2, ids=[transform.id]) == []

    async def test_repoint_transform_to_new_query_and_remove_old_query(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_old")],
                "jinja2_transforms": [_jinja2_transform_config(name="people_moving", query="people_old")],
            },
        )
        old_query = await client.get(kind=CoreGraphQLQuery, name__value="people_old")
        transform = await client.get(kind=CoreTransformJinja2, name__value="people_moving")
        assert transform.query.id == old_query.id

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_new")],
                "jinja2_transforms": [_jinja2_transform_config(name="people_moving", query="people_new")],
            },
        )

        new_query = await client.get(kind=CoreGraphQLQuery, name__value="people_new")
        moved_transform = await client.get(kind=CoreTransformJinja2, id=transform.id)
        assert moved_transform.query.id == new_query.id
        assert await client.filters(kind=CoreGraphQLQuery, ids=[old_query.id]) == []

    async def test_remove_generator_definition_with_its_query(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_generator")],
                "generator_definitions": [
                    {
                        "name": "people_generator",
                        "file_path": "generators/cartags.py",
                        "class_name": "Generator",
                        "targets": "people",
                        "query": "people_generator",
                        "parameters": {"name": "name__value"},
                    }
                ],
            },
        )
        query = await client.get(kind=CoreGraphQLQuery, name__value="people_generator")
        generator = await client.get(kind=CoreGeneratorDefinition, name__value="people_generator")
        assert generator.query.id == query.id

        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=BASE_CONFIG
        )

        assert await client.filters(kind=CoreGraphQLQuery, ids=[query.id]) == []
        assert await client.filters(kind=CoreGeneratorDefinition, ids=[generator.id]) == []

    async def test_remove_last_remaining_query(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        query = await client.get(kind=CoreGraphQLQuery, name__value="people_base")

        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config={}
        )

        assert await client.filters(kind=CoreGraphQLQuery, ids=[query.id]) == []


def _commit_config(file_repo: FileRepo, config: dict[str, Any]) -> str:
    (Path(file_repo.path) / ".infrahub.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    file_repo.repo.git.add(".")
    return file_repo.repo.index.commit("update repository config").hexsha
