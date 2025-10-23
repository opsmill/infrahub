from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import ANY, call, patch

import pytest

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.message_bus.types import ProposedChangeBranchDiff
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import (
    RequestProposedChangePipeline,
    RequestProposedChangeRefreshArtifacts,
    RequestProposedChangeRunGenerators,
)
from infrahub.proposed_change.tasks import run_generators, run_proposed_change_pipeline
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import (
    REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
    REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
    REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_USER_TESTS,
)
from tests.adapters.log import FakeLogger
from tests.adapters.message_bus import BusRecorder
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
      created_by {
        node {
          id
        }
      }
    }
  }
}
"""


class TestProposedChange(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def user_account(self, db: InfrahubDatabase) -> Node:
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="user", password="password")
        await account.save(db=db)
        return account

    @pytest.fixture(scope="class")
    async def context(self, user_account: Node) -> InfrahubContext:
        """Placeholder context for now, would be good to implement some auth and permissions here"""
        return InfrahubContext(
            account=AccountSession(authenticated=False, account_id=user_account.get_id(), auth_type=AuthType.NONE),
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
        user_account: Node,
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

        repo = await InfrahubRepository.new(id=obj.id, name=file_repo.name, location=file_repo.path, client=client)
        await repo.sync()  # type: ignore[call-overload]

        result = await graphql_mutation(
            query=PROPOSED_CHANGE_CREATE,
            variables={"name": "first", "source_branch": "change1", "destination_branch": "main"},
            db=db,
            service=service,
            account_session=context.account,
        )
        assert not result.errors
        assert result.data
        assert result.data["CoreProposedChangeCreate"]["object"]["created_by"]["node"]["id"] == user_account.get_id()
        proposed_change_id = result.data["CoreProposedChangeCreate"]["object"]["id"]

        pc = await NodeManager.get_one(db=db, id=proposed_change_id)
        created_by = await pc.created_by.get_peer(db=db)
        assert created_by.get_id() == user_account.get_id()

        return proposed_change_id

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
        with patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow:
            await run_proposed_change_pipeline(model=model, context=context)

            expected_calls_before_data_changes = [
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
                    parameters=ANY,
                    context=ANY,
                ),
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_USER_TESTS,
                    parameters=ANY,
                    context=ANY,
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls_before_data_changes)
            mock_submit_workflow.reset_mock()

            # Add an object to the source_branch to modify the data
            obj = await Node.init(db=db, schema=InfrahubKind.TAG, branch="change1")
            await obj.new(db=db, name="ci-pipeline-01", description="for use within tests")
            await obj.save(db=db)

            await run_proposed_change_pipeline(model=model, context=context)

            expected_calls_after_data_changes = [
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
                    parameters=ANY,
                    context=ANY,
                ),
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
                    parameters=ANY,
                    context=ANY,
                ),
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
                    parameters=ANY,
                    context=ANY,
                ),
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_USER_TESTS,
                    parameters=ANY,
                    context=ANY,
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls_after_data_changes)

    async def test_run_generators_validate_requested_jobs(
        self,
        prepare_proposed_change: str,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        client: InfrahubClient,
        context: InfrahubContext,
    ):
        pipeline_id = uuid.uuid4()
        model = RequestProposedChangeRunGenerators(
            source_branch="change1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            proposed_change=prepare_proposed_change,
            branch_diff=ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[], subscribers=[]),
            refresh_artifacts=True,
            do_repository_checks=True,
        )
        bus = BusRecorder()
        service = await InfrahubServices.new(
            client=client,
            cache=await InfrahubCache.new_from_driver(driver=config.SETTINGS.cache.driver),
            message_bus=bus,
            log=FakeLogger(),
            workflow=WorkflowLocalExecution(),
        )
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=[], cache=service.cache)
        with patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow:
            await run_generators(model=model, context=context)

            expected_calls = [
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
                    parameters={
                        "model": RequestProposedChangeRefreshArtifacts(
                            proposed_change=model.proposed_change,
                            source_branch=model.source_branch,
                            source_branch_sync_with_git=model.source_branch_sync_with_git,
                            destination_branch=model.destination_branch,
                            branch_diff=model.branch_diff,
                        )
                    },
                    context=ANY,
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls)
