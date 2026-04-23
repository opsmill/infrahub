from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, patch

import pytest
from infrahub_sdk.graphql import Mutation

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import BRANCH_DELETE
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestBranchDelete(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None: ...

    async def test_branch_delete_workflow(
        self,
        initial_dataset: None,
        client: InfrahubClient,
    ) -> None:
        branch = await client.branch.create(branch_name="branch-with-pc")

        pc = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={
                "name": {"value": "test-pc"},
                "source_branch": {"value": branch.name},
                "destination_branch": {"value": registry.default_branch},
                "is_draft": {"value": False},
            },
        )
        await pc.save()

        with patch.object(WorkflowLocalExecution, "execute_workflow", new_callable=AsyncMock) as mock_execute:
            query = Mutation(
                mutation="BranchDelete",
                input_data={"data": {"name": branch.name}},
                query={"ok": None},
            )
            await client.execute_graphql(query=query.render())

            mock_execute.assert_any_call(
                workflow=BRANCH_DELETE,
                context=ANY,
                parameters={"branch": branch.name, "proposed_change_id": pc.id, "delete_from_git": False},
            )
