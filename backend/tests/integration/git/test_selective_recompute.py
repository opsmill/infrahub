from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from infrahub_sdk.protocols import CoreTransformPython
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.constants import InfrahubKind
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.node_action import NodeUpdatedEvent
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.events import query_events_by_name
from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from prefect.events.schemas.events import Event

    from tests.helpers.file_repo import FileRepo


class TestSelectiveRecompute(FingerprintImportTestBase):
    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect: str) -> AsyncGenerator[PrefectClient, None]:
        # `prefect` sets PREFECT_API_URL to the same server the import flow publishes events to,
        # so the client reads the events a real import actually emitted.
        async with get_client(sync_client=False) as client:
            yield client

    async def test_import_emits_fingerprint_update_event_for_transform(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo, prefect_client: PrefectClient
    ) -> None:
        """A real import that changes a transform's fingerprint emits the node event the trigger matches.

        The update trigger keys on a node.updated event whose primary node is the transform and whose
        related resources carry a fingerprint attribute update. This proves the import produces exactly
        that event, tagged as a live edit.
        """
        transform = await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        transform_id = transform.id

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={
                "transforms/car_spec_markdown.py": (Path(file_repo.path) / "transforms/car_spec_markdown.py").read_text(
                    encoding="utf-8"
                )
                + "\n# event linkage marker\n"
            },
        )

        matching_event = await self._wait_for_fingerprint_update_event(
            prefect_client=prefect_client, transform_id=transform_id
        )
        assert matching_event is not None, "no node.updated event with a fingerprint attribute update for the transform"
        assert matching_event.resource["infrahub.node.kind"] == InfrahubKind.TRANSFORMPYTHON
        assert matching_event.resource[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE.value

    async def _wait_for_fingerprint_update_event(
        self, prefect_client: PrefectClient, transform_id: str
    ) -> Event | None:
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            events = await query_events_by_name(client=prefect_client, event_name=NodeUpdatedEvent.event_name)
            for event in events:
                if event.resource.get("infrahub.node.id") != transform_id:
                    continue
                if any(
                    related.role == "infrahub.node.attribute_update"
                    and related.get("infrahub.field.name") == "fingerprint"
                    for related in event.related
                ):
                    return event
            await asyncio.sleep(1)
        return None
