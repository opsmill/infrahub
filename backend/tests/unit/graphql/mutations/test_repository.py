from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import call, patch

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git.models import GitRepositoryImportObjects
from infrahub.graphql.mutations.repository import cleanup_payload
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import GIT_REPOSITORIES_IMPORT_OBJECTS
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_mutation
from tests.helpers.utils import init_global_service

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_trigger_repository_import(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
):
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=recorder, workflow=WorkflowLocalExecution())

    # TODO: Removing this mock triggers issue: `Invalid file system for test-edge-demo, local directory ... missing`
    with init_global_service(service), patch(
        "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
    ) as mock_submit_workflow:
        RUN_REIMPORT = """
        mutation InfrahubRepositoryProcess($id: String!) {
            InfrahubRepositoryProcess(data: {id: $id}) {
                ok
            }
        }
        """

        repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
        commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"
        await repo.new(db=db, name="test-edge-demo", location="/tmp/edge", commit=commit_id)
        await repo.save(db=db)
        result = await graphql_mutation(
            query=RUN_REIMPORT,
            db=db,
            variables={"id": repo.id},
            service=service,
        )

        assert not result.errors
        assert result.data

        expected_calls = [
            call(
                workflow=GIT_REPOSITORIES_IMPORT_OBJECTS,
                parameters={
                    "model": GitRepositoryImportObjects(
                        repository_id=repo.id,
                        repository_name=str(repo.name.value),
                        repository_kind=repo.get_kind(),
                        commit=commit_id,
                        infrahub_branch_name=default_branch.name,
                    )
                },
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)


async def test_repository_update(db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch):
    branch2 = await create_branch(branch_name="branch2", db=db)
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=recorder)

    UPDATE_COMMIT = """
    mutation CoreRepositoryUpdate($id: String!, $commit_id: String!, $internal_status: String!) {
        CoreRepositoryUpdate(
            data: {
                id: $id
                commit: { value: $commit_id }
                internal_status: { value: $internal_status }
            }) {
            ok
        }
    }
    """
    commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"

    # Create the repo in main
    repo = await Node.init(schema=repository_model, db=db, branch=branch2)
    await repo.new(db=db, name="test-edge-demo", location="/tmp/edge")
    await repo.save(db=db)

    repo.internal_status.value = RepositoryInternalStatus.STAGING.value
    await repo.save(db=db)

    result = await graphql_mutation(
        query=UPDATE_COMMIT,
        db=db,
        variables={"id": repo.id, "commit_id": commit_id, "internal_status": RepositoryInternalStatus.ACTIVE.value},
        service=service,
    )

    assert not result.errors
    assert result.data

    repo_main = await NodeManager.get_one(db=db, id=repo.id, raise_on_error=True)

    assert repo_main.internal_status.value == RepositoryInternalStatus.ACTIVE.value
    assert repo_main.commit.value == commit_id


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ({"location": {"value": "/tmp/repo_dir"}}, {"location": {"value": "/tmp/repo_dir"}}),
        (
            {"location": {"value": "https://github.com/opsmill/infrahub-demo-edge-develop"}},
            {"location": {"value": "https://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
        (
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop"}},
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
        (
            {"name": "demo"},
            {"name": "demo"},
        ),
        (
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
    ],
)
def test_cleanup_payload(test_input, expected):
    cleanup_payload(data=test_input)
    assert test_input == expected
