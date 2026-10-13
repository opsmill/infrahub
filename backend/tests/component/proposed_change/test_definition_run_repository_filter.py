from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.generators.tasks import run_generator_definition
from infrahub.git.tasks import generate_artifact_definition
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_GENERATOR_DEFINITION_RUN

from .conftest import ArtifactRegenTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder

TAG_QUERY = "query GetTags { BuiltinTag { edges { node { name { value } } } } }"
REPOSITORY_NAMES = ("repo-a", "repo-b")


@dataclass(frozen=True, kw_only=True)
class RepositoryFilterCase:
    name: str
    exclude: list[str] | None
    include: list[str] | None
    expected_repositories: set[str]
    """The repositories whose definitions the run submits."""


REPOSITORY_FILTER_CASES = [
    RepositoryFilterCase(
        name="no_filter_submits_every_definition",
        exclude=None,
        include=None,
        expected_repositories={"repo-a", "repo-b"},
    ),
    RepositoryFilterCase(
        name="excluded_repository_is_skipped", exclude=["repo-a"], include=None, expected_repositories={"repo-b"}
    ),
    RepositoryFilterCase(
        name="include_list_keeps_only_its_repositories",
        exclude=None,
        include=["repo-a"],
        expected_repositories={"repo-a"},
    ),
]


class TestDefinitionRunRepositoryFilter(ArtifactRegenTestBase):
    """A run over every artifact or generator definition skips the definitions of the filtered repositories."""

    @pytest.fixture(scope="class")
    async def repository_ids(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient
    ) -> dict[str, str]:
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetTags", query=TAG_QUERY, models=[InfrahubKind.TAG])
        await query.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="filter-targets")
        await group.save(db=db)

        repository_ids: dict[str, str] = {}
        for name in REPOSITORY_NAMES:
            repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
            await repository.new(db=db, name=name, location=f"https://github.com/test/{name}.git")
            await repository.save(db=db)
            repository_ids[name] = repository.id

            transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
            await transform.new(
                db=db, name=f"{name}-transform", query=query, repository=repository, template_path="templates/t.j2"
            )
            await transform.save(db=db)
            artifact_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
            await artifact_definition.new(
                db=db,
                name=f"{name}-artifact",
                targets=group,
                transformation=transform,
                content_type="text/plain",
                artifact_name=f"{name}-config",
                parameters={"value": {"name": "name__value"}},
            )
            await artifact_definition.save(db=db)

            generator_definition = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
            await generator_definition.new(
                db=db,
                name=f"{name}-generator",
                query=query,
                repository=repository,
                targets=group,
                file_path="generators/g.py",
                class_name="Generator",
                parameters={"value": {"name": "name__value"}},
            )
            await generator_definition.save(db=db)
        return repository_ids

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REPOSITORY_FILTER_CASES])
    async def test_artifact_definition_run(
        self,
        case: RepositoryFilterCase,
        repository_ids: dict[str, str],
        default_branch: Branch,
        admin_account: CoreAccount,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await generate_artifact_definition(
            branch=default_branch.name,
            context=self._make_context(admin_account, default_branch),
            exclude_repository_ids=_ids(names=case.exclude, repository_ids=repository_ids),
            include_repository_ids=_ids(names=case.include, repository_ids=repository_ids),
        )

        submitted = {
            call["parameters"]["model"].artifact_definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
        }
        assert submitted == {f"{name}-artifact" for name in case.expected_repositories}

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REPOSITORY_FILTER_CASES])
    async def test_generator_definition_run(
        self,
        case: RepositoryFilterCase,
        repository_ids: dict[str, str],
        default_branch: Branch,
        admin_account: CoreAccount,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await run_generator_definition(
            branch=default_branch.name,
            context=self._make_context(admin_account, default_branch),
            exclude_repository_ids=_ids(names=case.exclude, repository_ids=repository_ids),
            include_repository_ids=_ids(names=case.include, repository_ids=repository_ids),
        )

        submitted = {
            call["parameters"]["model"].generator_definition.definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN)
        }
        assert submitted == {f"{name}-generator" for name in case.expected_repositories}


def _ids(*, names: list[str] | None, repository_ids: dict[str, str]) -> list[str] | None:
    return None if names is None else [repository_ids[name] for name in names]
