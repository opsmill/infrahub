from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect import get_client
from tests.helpers.test_app import TestInfrahubApp

from infrahub import config
from infrahub.core.constants.infrahubkind import CHANGETHREAD, PROPOSEDCHANGE, THREADCOMMENT
from infrahub.core.initialization import create_branch

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestProposedChangeThreadEvents(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def enable_broker_settings(self) -> None:
        config.SETTINGS.broker.enable = True

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    async def test_thread_events(
        self,
        enable_broker_settings: None,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
        prefect_client: PrefectClient,
    ) -> None:
        """
        Create a proposed change thread and then mark it as resolved all of this while asserting that events are being fired.
        """
        source_branch = await create_branch(branch_name="branch-proposed-change", db=db)
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc"},
        )
        await proposed_change.save()

        pc_thread = await client.create(kind=CHANGETHREAD, data={"change": proposed_change.id})
        await pc_thread.save()

        pc_thread_comment = await client.create(kind=THREADCOMMENT, data={"thread": pc_thread.id, "text": "A comment"})
        await pc_thread_comment.save()

        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change_thread.created")

        pc_thread.resolved.value = True
        await pc_thread.save()

        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change_thread.updated")
