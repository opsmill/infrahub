from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreGeneratorDefinition,
    CoreGraphQLQuery,
    CoreReadOnlyRepository,
    CoreStandardGroup,
    CoreTransformJinja2,
    CoreTransformPython,
)

from infrahub.core.constants import InfrahubKind, RepositorySyncStatus
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryConfigurationError
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


class PeopleNames(InfrahubTransform):
    query = "people_report"

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"names": [edge["node"]["name"]["value"] for edge in data["TestingPerson"]["edges"]]}
"""

PEOPLE_CHECK = """from infrahub_sdk.checks import InfrahubCheck


class PeopleExist(InfrahubCheck):
    query = "people_report"

    def validate(self, data: dict) -> None:
        if not data["TestingPerson"]["edges"]:
            self.log_error(message="No people found")


class PeopleNamed(InfrahubCheck):
    query = "people_report"

    def validate(self, data: dict) -> None:
        for edge in data["TestingPerson"]["edges"]:
            if not edge["node"]["name"]["value"]:
                self.log_error(message="A person has no name")
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
    "checks/people_check.py": PEOPLE_CHECK,
    "templates/people.j2": PEOPLE_TEMPLATE,
}


def _query_config(name: str) -> dict[str, str]:
    return {"name": name, "file_path": f"queries/{name}.gql"}


# A query every commit keeps, so a removal commit still declares queries, as a real repository does.
BASE_QUERY = _query_config(name="people_base")
BASE_CONFIG: dict[str, Any] = {"queries": [BASE_QUERY]}


def _jinja2_transform_config(name: str, query: str) -> dict[str, str]:
    return {"name": name, "query": query, "template_path": "templates/people.j2"}


def _people_report_transform_config(name: str, class_name: str = "PeopleReport") -> dict[str, str]:
    return {"name": name, "class_name": class_name, "file_path": "transforms/people_report.py"}


def _people_check_config(class_name: str, targets: str | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {"name": "people check", "class_name": class_name, "file_path": "checks/people_check.py"}
    if targets:
        config["targets"] = targets
        config["parameters"] = {"name": "name__value"}
    return config


def _people_report_artifact_definition_config(transformation: str) -> dict[str, Any]:
    return {
        "name": "people report",
        "artifact_name": "people-report",
        "parameters": {"name": "name__value"},
        "content_type": "application/json",
        "targets": "people",
        "transformation": transformation,
    }


class TestImportRemovedDefinitions(TestInfrahubApp):
    """Changing objects in the repository config updates them, and removing them deletes them whatever else references them."""

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
        adults = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await adults.new(db=db, name="adults", members=[john])
        await adults.save(db=db)

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
        await self._import_last_commit(service=service, repository_id=repository_id)

        repository = await client.get(kind=CoreReadOnlyRepository, id=repository_id)
        assert repository.commit.value == commit
        assert repository.sync_status.value == RepositorySyncStatus.IN_SYNC.value

    async def _import_last_commit(self, service: InfrahubServices, repository_id: str) -> None:
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

    async def test_repoint_artifact_definition_to_new_transform_and_keep_old_transform(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [_people_report_transform_config(name="PeopleReport")],
                "artifact_definitions": [_people_report_artifact_definition_config(transformation="PeopleReport")],
            },
        )
        old_transform = await client.get(kind=CoreTransformPython, name__value="PeopleReport")
        artifact_definition = await client.get(kind=CoreArtifactDefinition, name__value="people report")
        assert artifact_definition.transformation.id == old_transform.id

        repointed_config: dict[str, Any] = {
            "queries": [BASE_QUERY, _query_config(name="people_report")],
            "python_transforms": [
                _people_report_transform_config(name="PeopleReport"),
                _people_report_transform_config(name="PeopleSummary"),
            ],
            "artifact_definitions": [_people_report_artifact_definition_config(transformation="PeopleSummary")],
        }
        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=repointed_config
        )
        new_transform = await client.get(kind=CoreTransformPython, name__value="PeopleSummary")
        moved_artifact_definition = await client.get(
            kind=CoreArtifactDefinition, id=artifact_definition.id, property=True
        )
        assert moved_artifact_definition.transformation.id == new_transform.id
        assert moved_artifact_definition.transformation.source == repository_id
        assert moved_artifact_definition.transformation.is_protected is True
        kept_transform = await client.get(kind=CoreTransformPython, id=old_transform.id)
        assert kept_transform.name.value == "PeopleReport"

    async def test_resync_repoints_artifact_definition_whose_fingerprint_is_current(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        # Watching the source file keeps the fingerprints the same across commits.
        watch = {"watch": {"files": ["transforms/people_report.py"]}}
        config: dict[str, Any] = {
            "queries": [BASE_QUERY, _query_config(name="people_report")],
            "python_transforms": [
                {**_people_report_transform_config(name="PeopleReport"), **watch},
                {**_people_report_transform_config(name="PeopleSummary"), **watch},
            ],
            "artifact_definitions": [_people_report_artifact_definition_config(transformation="PeopleSummary")],
        }
        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=config
        )
        declared_transform = await client.get(kind=CoreTransformPython, name__value="PeopleSummary")
        other_transform = await client.get(kind=CoreTransformPython, name__value="PeopleReport")
        artifact_definition = await client.get(kind=CoreArtifactDefinition, name__value="people report")
        fingerprint = artifact_definition.fingerprint.value
        artifact_definition.transformation = other_transform.id
        await artifact_definition.save()
        drifted_artifact_definition = await client.get(kind=CoreArtifactDefinition, id=artifact_definition.id)
        assert drifted_artifact_definition.transformation.id == other_transform.id
        assert drifted_artifact_definition.fingerprint.value == fingerprint

        await self._commit_and_sync(
            client=client, service=service, repository_id=repository_id, file_repo=file_repo, config=config
        )

        resynced_artifact_definition = await client.get(kind=CoreArtifactDefinition, id=artifact_definition.id)
        assert resynced_artifact_definition.fingerprint.value == fingerprint
        assert resynced_artifact_definition.transformation.id == declared_transform.id

    async def test_rename_transform_of_artifact_definition_and_remove_old_transform(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [_people_report_transform_config(name="PeopleReport")],
                "artifact_definitions": [_people_report_artifact_definition_config(transformation="PeopleReport")],
            },
        )
        old_transform = await client.get(kind=CoreTransformPython, name__value="PeopleReport")
        artifact_definition = await client.get(kind=CoreArtifactDefinition, name__value="people report")
        assert artifact_definition.transformation.id == old_transform.id

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [_people_report_transform_config(name="PeopleSummary")],
                "artifact_definitions": [_people_report_artifact_definition_config(transformation="PeopleSummary")],
            },
        )

        renamed_transform = await client.get(kind=CoreTransformPython, name__value="PeopleSummary")
        moved_artifact_definition = await client.get(
            kind=CoreArtifactDefinition, id=artifact_definition.id, property=True
        )
        assert moved_artifact_definition.transformation.id == renamed_transform.id
        assert moved_artifact_definition.transformation.source == repository_id
        assert moved_artifact_definition.transformation.is_protected is True
        assert await client.filters(kind=CoreTransformPython, ids=[old_transform.id]) == []

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

    async def test_change_class_name_of_python_transform(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [_people_report_transform_config(name="PeopleReport")],
            },
        )
        transform = await client.get(kind=CoreTransformPython, name__value="PeopleReport")
        assert transform.class_name.value == "PeopleReport"

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "python_transforms": [_people_report_transform_config(name="PeopleReport", class_name="PeopleNames")],
            },
        )

        updated_transform = await client.get(kind=CoreTransformPython, id=transform.id)
        assert updated_transform.class_name.value == "PeopleNames"

    async def test_change_class_name_of_check_definition(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "check_definitions": [_people_check_config(class_name="PeopleExist")],
            },
        )
        check_definition = await client.get(kind=CoreCheckDefinition, name__value="people check")
        assert check_definition.class_name.value == "PeopleExist"

        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "check_definitions": [_people_check_config(class_name="PeopleNamed")],
            },
        )

        updated_check_definition = await client.get(kind=CoreCheckDefinition, id=check_definition.id)
        assert updated_check_definition.class_name.value == "PeopleNamed"

    async def test_change_targets_of_check_definition(
        self, client: InfrahubClient, service: InfrahubServices, repository_id: str, file_repo: FileRepo
    ) -> None:
        people = await client.get(kind=CoreStandardGroup, name__value="people")
        adults = await client.get(kind=CoreStandardGroup, name__value="adults")
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "check_definitions": [_people_check_config(class_name="PeopleExist")],
            },
        )
        check_definition = await client.get(kind=CoreCheckDefinition, name__value="people check")
        assert check_definition.targets.id is None

        for targets, expected_target_id in (("people", people.id), ("adults", adults.id), (None, None)):
            await self._commit_and_sync(
                client=client,
                service=service,
                repository_id=repository_id,
                file_repo=file_repo,
                config={
                    "queries": [BASE_QUERY, _query_config(name="people_report")],
                    "check_definitions": [_people_check_config(class_name="PeopleExist", targets=targets)],
                },
            )
            updated_check_definition = await client.get(kind=CoreCheckDefinition, id=check_definition.id)
            assert updated_check_definition.targets.id == expected_target_id, f"targets={targets}"

    async def test_check_definition_targeting_missing_group_fails_import(
        self,
        client: InfrahubClient,
        service: InfrahubServices,
        repository_id: str,
        file_repo: FileRepo,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await self._commit_and_sync(
            client=client,
            service=service,
            repository_id=repository_id,
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "check_definitions": [_people_check_config(class_name="PeopleExist")],
            },
        )
        check_definition = await client.get(kind=CoreCheckDefinition, name__value="people check")
        assert check_definition.targets.id is None

        _commit_config(
            file_repo=file_repo,
            config={
                "queries": [BASE_QUERY, _query_config(name="people_report")],
                "check_definitions": [_people_check_config(class_name="PeopleExist", targets="missing")],
            },
        )
        expected_message = (
            f"Check definition 'people check' in repository '{REPOSITORY_NAME}' targets the group 'missing', "
            "but no group named 'missing' exists on branch 'main'."
        )
        with pytest.raises(RepositoryConfigurationError, match=rf"^{re.escape(expected_message)}$"):
            await self._import_last_commit(service=service, repository_id=repository_id)

        assert expected_message in [record.getMessage() for record in caplog.records if record.levelname == "ERROR"]
        repository = await client.get(kind=CoreReadOnlyRepository, id=repository_id)
        assert repository.sync_status.value == RepositorySyncStatus.ERROR_IMPORT.value
        unchanged_check_definition = await client.get(kind=CoreCheckDefinition, id=check_definition.id)
        assert unchanged_check_definition.targets.id is None

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
