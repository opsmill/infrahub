from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, patch

import pytest
from infrahub_sdk.graphql import Mutation

from infrahub import config
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import GIT_REPOSITORIES_DELETE_BRANCH
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestDeleteBranchGitWorkflow(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

    async def test_git_deletion_triggered_when_config_enabled_and_sync_with_git(
        self, initial_dataset: None, client: InfrahubClient, delete_git_branch_after_merge_reset_config: None
    ) -> None:
        config.SETTINGS.git.delete_git_branch_after_merge = True
        branch = await client.branch.create(branch_name="git_del_cfg_enabled", sync_with_git=True)

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            query = Mutation(
                mutation="BranchDelete",
                input_data={"data": {"name": branch.name}},
                query={"ok": None},
            )
            await client.execute_graphql(query=query.render())

            mock_submit.assert_any_call(
                workflow=GIT_REPOSITORIES_DELETE_BRANCH,
                context=ANY,
                parameters={"branch": branch.name},
            )

    async def test_git_deletion_not_triggered_when_config_disabled(
        self, initial_dataset: None, client: InfrahubClient, delete_git_branch_after_merge_reset_config: None
    ) -> None:
        config.SETTINGS.git.delete_git_branch_after_merge = False
        branch = await client.branch.create(branch_name="git_del_cfg_disabled", sync_with_git=True)

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            query = Mutation(
                mutation="BranchDelete",
                input_data={"data": {"name": branch.name}},
                query={"ok": None},
            )
            await client.execute_graphql(query=query.render())

            git_del_calls = [
                c for c in mock_submit.call_args_list if c.kwargs.get("workflow") == GIT_REPOSITORIES_DELETE_BRANCH
            ]
            assert not git_del_calls

    async def test_git_deletion_not_triggered_when_branch_not_sync_with_git(
        self, initial_dataset: None, client: InfrahubClient, delete_git_branch_after_merge_reset_config: None
    ) -> None:
        config.SETTINGS.git.delete_git_branch_after_merge = True
        branch = await client.branch.create(branch_name="git_del_no_sync", sync_with_git=False)

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            query = Mutation(
                mutation="BranchDelete",
                input_data={"data": {"name": branch.name}},
                query={"ok": None},
            )
            await client.execute_graphql(query=query.render())

            git_del_calls = [
                c for c in mock_submit.call_args_list if c.kwargs.get("workflow") == GIT_REPOSITORIES_DELETE_BRANCH
            ]
            assert not git_del_calls
