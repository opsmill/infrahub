from __future__ import annotations

import os
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.message_bus.operations.requests.proposed_change import pipeline
from infrahub.server import app, app_initialization
from infrahub.services import InfrahubServices, services
from tests.adapters.log import FakeLogger
from tests.adapters.message_bus import BusRecorder
from tests.helpers.file_repo import FileRepo
from tests.helpers.graphql import graphql_mutation
from tests.helpers.test_client import InfrahubTestClient
from tests.integration.conftest import IntegrationHelper

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

BRANCH_CREATE = """
    mutation($branch: String!) {
        BranchCreate(data: {
                name: $branch
            }) {
            ok
            object {
                id
                name
            }
        }
    }
"""

PROPOSED_CHANGE_CREATE = """
mutation ProposedChange(
  $name: String!,
  $source_branch: String!,
  $destination_branch: String!,
	) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source_branch},
      destination_branch: {value: $destination_branch}
    }
  ) {
    object {
      id
    }
  }
}
"""


@pytest.fixture(scope="module")
async def test_client(init_db_base) -> AsyncGenerator[InfrahubTestClient, None]:
    await app_initialization(app)
    async with InfrahubTestClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="module")
async def prepare_proposed_change(
    db: InfrahubDatabase,
    tmp_path_module_scope,
    git_repos_dir_module_scope: str,
    init_db_base,
    test_client: InfrahubTestClient,
) -> str:
    source_dir = os.path.join(str(tmp_path_module_scope), "sources")
    os.mkdir(source_dir)
    file_repo = FileRepo(name="conflict-01", sources_directory=source_dir)

    obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
    await obj.new(
        db=db,
        name=file_repo.name,
        description="test repository",
        location=file_repo.path,
        commit=file_repo.repo.commit("main").hexsha,
    )
    await obj.save(db=db)

    bus = BusRecorder()
    integration_helper = IntegrationHelper(db=db)

    admin_token = await integration_helper.create_token()

    config = Config(api_token=admin_token, requester=test_client.async_request)
    client = InfrahubClient(config=config)

    service = InfrahubServices(message_bus=bus, client=client)
    services.prepare(service=service)

    repo = await InfrahubRepository.new(id=obj.id, name=file_repo.name, location=file_repo.path, client=client)

    await repo.sync()

    result = await graphql_mutation(
        query=PROPOSED_CHANGE_CREATE,
        variables={"name": "first", "source_branch": "change1", "destination_branch": "main"},
        db=db,
    )
    assert not result.errors
    assert result.data
    return result.data["CoreProposedChangeCreate"]["object"]["id"]


async def test_run_pipeline_validate_requested_jobs(
    prepare_proposed_change: str,
    db: InfrahubDatabase,
    test_client: InfrahubTestClient,
):
    message = messages.RequestProposedChangePipeline(
        source_branch="change1",
        source_branch_data_only=False,
        destination_branch="main",
        proposed_change=prepare_proposed_change,
    )
    integration_helper = IntegrationHelper(db=db)
    bus_pre_data_changes = BusRecorder()
    admin_token = await integration_helper.create_token()
    config = Config(api_token=admin_token, requester=test_client.async_request)
    client = InfrahubClient(config=config)
    fake_log = FakeLogger()
    services.service._client = client
    services.service.log = fake_log
    services.service.message_bus = bus_pre_data_changes
    services.prepare(service=services.service)
    await pipeline(message=message, service=services.service)

    # Add an object to the source_branch to modify the data
    obj = await Node.init(db=db, schema=InfrahubKind.TAG, branch="change1")
    await obj.new(db=db, name="ci-pipeline-01", description="for use within tests")
    await obj.save(db=db)

    bus_post_data_changes = BusRecorder()
    services.service.message_bus = bus_post_data_changes
    services.prepare(service=services.service)
    await pipeline(message=message, service=services.service)

    assert sorted(bus_pre_data_changes.seen_routing_keys) == [
        "request.proposed_change.refresh_artifacts",
        "request.proposed_change.repository_checks",
        "request.proposed_change.run_tests",
    ]

    assert sorted(bus_post_data_changes.seen_routing_keys) == [
        "request.proposed_change.data_integrity",
        "request.proposed_change.refresh_artifacts",
        "request.proposed_change.repository_checks",
        "request.proposed_change.run_tests",
        "request.proposed_change.schema_integrity",
    ]
