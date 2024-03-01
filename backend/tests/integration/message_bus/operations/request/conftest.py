from __future__ import annotations

import os
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.server import app, app_initialization
from infrahub.services import InfrahubServices, services
from tests.adapters.message_bus import BusRecorder
from tests.helpers.file_repo import FileRepo
from tests.helpers.graphql import graphql_mutation
from tests.helpers.test_client import InfrahubTestClient
from tests.integration.conftest import IntegrationHelper

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


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
