from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

from prefect import flow, tags
from prefect.context import AsyncClientContext
from prefect.runtime import flow_run

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    import httpx
    from prefect.client.orchestration import PrefectClient

ADDED_TAGS = {
    "infrahub.app",
    "infrahub.app/branch/feature",
    "infrahub.app/node/node-1",
    "custom",
    "infrahub.app/database-change",
}


@flow(name="add-tags-under-test")
async def _tagging_flow() -> str:
    await add_tags(branches=["feature", GLOBAL_BRANCH_NAME], nodes=["node-1"], others=["custom"], db_change=True)
    return flow_run.id


async def test_add_tags_merges_into_the_tags_the_run_started_with(prefect_client: PrefectClient) -> None:
    with tags("set-at-creation"):
        flow_run_id = await _tagging_flow()

    run = await prefect_client.read_flow_run(flow_run_id=UUID(flow_run_id))

    assert set(run.tags) == {"set-at-creation", *ADDED_TAGS}


async def test_add_tags_updates_the_run_through_the_running_flow_client() -> None:
    sent: list[httpx.Request] = []

    async def record(request: httpx.Request) -> None:
        sent.append(request)

    async with AsyncClientContext(httpx_settings={"event_hooks": {"request": [record]}}):
        flow_run_id = await _tagging_flow()

    run_path = f"/flow_runs/{flow_run_id}"
    state_updates = [request for request in sent if request.url.path.endswith(f"{run_path}/set_state")]
    tag_updates = [
        json.loads(request.content)["tags"]
        for request in sent
        if request.method == "PATCH" and request.url.path.endswith(run_path) and b'"tags"' in request.content
    ]

    # The run's own state changes prove the recording client is the one the flow ran with.
    assert state_updates
    assert len(tag_updates) == 1
    assert set(tag_updates[0]) == ADDED_TAGS
