from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.message_bus.types import ProposedChangeBranchDiff
from infrahub.proposed_change.models import RequestProposedChangePipeline, RequestProposedChangeRunGenerators
from infrahub.proposed_change.tasks import run_generators, run_proposed_change_pipeline
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.log import FakeLogger
from tests.adapters.message_bus import BusRecorder, BusSimulator
from tests.helpers.file_repo import FileRepo
from tests.helpers.graphql import graphql_mutation
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

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


class TestProposedChange(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def context(self) -> InfrahubContext:
        """Placeholder context for now, would be good to implement some auth and permissions here"""
        return InfrahubContext(
            account=AccountSession(authenticated=False, account_id="placeholder", auth_type=AuthType.NONE),
            branch=BranchContext(name="main", id="placeholder"),
        )

    @pytest.fixture(scope="class")
    async def prepare_proposed_change(
        self,
        db: InfrahubDatabase,
        tmp_path_module_scope,
        git_repos_dir_module_scope: Path,
        init_db_base,
        client: InfrahubClient,
        redis,
        context: InfrahubContext,
    ) -> str:
        source_dir = tmp_path_module_scope / "sources"
        source_dir.mkdir()
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

        service = await InfrahubServices.new(
            message_bus=bus, client=client, workflow=WorkflowLocalExecution(), database=db, cache=RedisCache()
        )

        repo = await InfrahubRepository.new(
            id=obj.id, name=file_repo.name, location=file_repo.path, client=client, service=service
        )
        await repo.sync()

        result = await graphql_mutation(
            query=PROPOSED_CHANGE_CREATE,
            variables={"name": "first", "source_branch": "change1", "destination_branch": "main"},
            db=db,
            service=service,
            account_session=context.account,
        )
        assert not result.errors
        assert result.data
        return result.data["CoreProposedChangeCreate"]["object"]["id"]

    async def test_run_pipeline_validate_requested_jobs(
        self,
        prepare_proposed_change: str,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        client: InfrahubClient,
        context: InfrahubContext,
    ):
        model = RequestProposedChangePipeline(
            source_branch="change1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            proposed_change=prepare_proposed_change,
        )
        bus_pre_data_changes = BusRecorder()
        fake_log = FakeLogger()
        service = await InfrahubServices.new(
            client=client,
            log=fake_log,
            message_bus=bus_pre_data_changes,
            database=db,
            workflow=WorkflowLocalExecution(),
        )
        await run_proposed_change_pipeline(model=model, service=service, context=context)

        # Add an object to the source_branch to modify the data
        obj = await Node.init(db=db, schema=InfrahubKind.TAG, branch="change1")
        await obj.new(db=db, name="ci-pipeline-01", description="for use within tests")
        await obj.save(db=db)

        bus_post_data_changes = BusSimulator()
        service._message_bus = bus_post_data_changes
        bus_post_data_changes.service = service

        await run_proposed_change_pipeline(model=model, service=service, context=context)

    async def test_run_generators_validate_requested_jobs(
        self,
        prepare_proposed_change: str,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        client: InfrahubClient,
        context: InfrahubContext,
    ):
        model = RequestProposedChangeRunGenerators(
            source_branch="change1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            proposed_change=prepare_proposed_change,
            branch_diff=ProposedChangeBranchDiff(diff_summary=[], repositories=[], subscribers=[]),
            refresh_artifacts=True,
            do_repository_checks=True,
        )
        bus = BusRecorder()
        service = await InfrahubServices.new(
            client=client,
            message_bus=bus,
            log=FakeLogger(),
            workflow=WorkflowLocalExecution(),
        )
        await run_generators(model=model, context=context, service=service)
