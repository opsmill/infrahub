from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, patch

import pytest
from infrahub_sdk.graphql import Mutation

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import BRANCH_DELETE
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestAutoDeleteBranchAfterMerge(TestInfrahubApp):
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

    async def test_branch_auto_deleted_after_standard_merge_when_config_enabled(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        config.SETTINGS.main.delete_branch_after_merge = True
        branch = await client.branch.create(branch_name="auto_delete_standard_enabled")

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            query = Mutation(
                mutation="BranchMerge",
                input_data={"data": {"name": branch.name}},
                query={"ok": None, "task": {"id": None}, "object": {"id": None}},
            )
            await client.execute_graphql(query=query.render())

            mock_submit.assert_any_call(
                workflow=BRANCH_DELETE,
                context=ANY,
                parameters={"branch": branch.name},
            )

    async def test_branch_not_deleted_after_standard_merge_when_config_disabled(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        config.SETTINGS.main.delete_branch_after_merge = False
        branch = await client.branch.create(branch_name="auto_delete_standard_disabled")

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            query = Mutation(
                mutation="BranchMerge",
                input_data={"data": {"name": branch.name}},
                query={"ok": None, "task": {"id": None}, "object": {"id": None}},
            )
            await client.execute_graphql(query=query.render())

            delete_calls = [c for c in mock_submit.call_args_list if c.kwargs.get("workflow") == BRANCH_DELETE]
            assert not delete_calls

    async def test_branch_auto_deleted_after_proposed_change_merge(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        config.SETTINGS.main.delete_branch_after_merge = True
        branch = await client.branch.create(branch_name="auto_delete_pc_enabled")

        pc = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={
                "name": {"value": "test-pc-auto-delete"},
                "source_branch": {"value": branch.name},
                "destination_branch": {"value": registry.default_branch},
                "is_draft": {"value": False},
            },
        )
        await pc.save()

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            update_query = Mutation(
                mutation="CoreProposedChangeUpdate",
                input_data={"data": {"id": pc.id, "state": {"value": "merged"}}},
                query={"ok": None, "object": {"state": {"value": None}}},
            )
            await client.execute_graphql(query=update_query.render())

            mock_submit.assert_any_call(
                workflow=BRANCH_DELETE,
                context=ANY,
                parameters={"branch": branch.name},
            )

    @pytest.mark.skip("Multiple proposed changes are not allowed for the same branch")
    async def test_branch_not_deleted_when_other_open_proposed_changes_exist(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        config.SETTINGS.main.delete_branch_after_merge = True
        branch = await client.branch.create(branch_name="auto_delete_pc_other_open")

        pc1 = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={
                "name": {"value": "pc-open-1"},
                "source_branch": {"value": branch.name},
                "destination_branch": {"value": registry.default_branch},
                "is_draft": {"value": False},
            },
        )
        await pc1.save()

        pc2 = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={
                "name": {"value": "pc-open-2"},
                "source_branch": {"value": branch.name},
                "destination_branch": {"value": "pc-open-1"},
                "is_draft": {"value": False},
            },
        )
        await pc2.save()

        with patch.object(WorkflowLocalExecution, "submit_workflow", new_callable=AsyncMock) as mock_submit:
            update_query = Mutation(
                mutation="CoreProposedChangeUpdate",
                input_data={"data": {"id": pc1.id, "state": {"value": "merged"}}},
                query={"ok": None, "object": {"state": {"value": None}}},
            )
            await client.execute_graphql(query=update_query.render())

            delete_calls = [c for c in mock_submit.call_args_list if c.kwargs.get("workflow") == BRANCH_DELETE]
            assert not delete_calls
