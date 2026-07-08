from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
import pytest
import ujson
from infrahub_sdk import Config, InfrahubClient
from prefect.client.schemas.filters import FlowFilter, FlowFilterName
from prefect.client.schemas.objects import State, StateType
from prefect.client.schemas.sorting import FlowRunSort

from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.webhook.constants import CACHE_KEY_PREFIX
from infrahub.webhook.models import CustomWebhook
from infrahub.webhook.tasks import process
from infrahub.workers.dependencies import build_cache, build_client, build_http_service
from tests.adapters.cache import MemoryCache
from tests.adapters.http import MemoryHTTP

if TYPE_CHECKING:
    import ssl
    from uuid import UUID

    from fast_depends import Provider
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun

TARGET_URL = "https://cancel.example.test/hook"
RETRY_DELAY_SECONDS = 10.0
POLL_INTERVAL_SECONDS = 0.2
DISCOVERY_TIMEOUT_SECONDS = 30.0


class CountingHTTP(MemoryHTTP):
    """Record how many POSTs were made, on top of the canned responses."""

    def __init__(self) -> None:
        super().__init__()
        self.post_count = 0

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | ssl.SSLContext | None = None,
    ) -> httpx.Response:
        self.post_count += 1
        return await super().post(url=url, data=data, json=json, headers=headers, verify=verify)


@pytest.fixture
def failing_target() -> CountingHTTP:
    http = CountingHTTP()
    http.add_post_response(
        url=TARGET_URL,
        response=httpx.Response(request=httpx.Request(method="POST", url=TARGET_URL), status_code=500),
    )
    return http


def seeded_cache(webhook_id: str) -> MemoryCache:
    """Return a cache holding the webhook config, so resolution needs no database."""
    cache = MemoryCache()
    webhook = CustomWebhook(name="cancel-me", url=TARGET_URL, event_type="all", validate_certificates=False)
    cache.storage[f"{CACHE_KEY_PREFIX}:{webhook_id}"] = ujson.dumps(webhook.to_cache())
    return cache


async def wait_for_retry_wait(prefect_client: PrefectClient, known_run_ids: set[UUID]) -> FlowRun:
    """Return the new delivery run once its first attempt failed and it awaits its retry.

    Raises:
        TimeoutError: When no delivery reaches its retry wait within the discovery timeout.

    """
    deadline = asyncio.get_running_loop().time() + DISCOVERY_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        runs = await prefect_client.read_flow_runs(
            flow_filter=FlowFilter(name=FlowFilterName(any_=["webhook-send"])),
            sort=FlowRunSort.START_TIME_DESC,
            limit=10,
        )
        for run in runs:
            if run.id in known_run_ids or run.state is None:
                continue
            if run.state.type == StateType.SCHEDULED and run.state.name == "AwaitingRetry":
                return run
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("The delivery never reached its retry wait.")


async def read_send_run_ids(prefect_client: PrefectClient) -> set[UUID]:
    runs = await prefect_client.read_flow_runs(
        flow_filter=FlowFilter(name=FlowFilterName(any_=["webhook-send"])), limit=200
    )
    return {run.id for run in runs}


async def test_cancel_during_retry_wait_stops_remaining_attempts(
    prefect_client: PrefectClient,
    dependency_provider: Provider,
    failing_target: CountingHTTP,
) -> None:
    """Cancelling a delivery between attempts must stop the remaining attempts.

    The delivery is driven to its retry wait against a real Prefect server, then cancelled through
    the same call path the cancel mutation uses. No further attempt may reach the target, and the
    run must settle as cancelled.
    """
    webhook_id = str(uuid4())
    send = process.webhook_send.with_options(retries=1, retry_delay_seconds=RETRY_DELAY_SECONDS)

    with (
        dependency_provider.scope(build_http_service, lambda: failing_target),
        dependency_provider.scope(build_cache, lambda: seeded_cache(webhook_id)),
        # The webhook config is served from the seeded cache, so the client is never called;
        # a bare one satisfies resolution without the runtime registry the real builder needs.
        dependency_provider.scope(
            build_client, lambda: InfrahubClient(config=Config(address="http://unused.example.test"))
        ),
    ):
        known_run_ids = await read_send_run_ids(prefect_client)
        delivery = asyncio.create_task(
            send(
                webhook_id=webhook_id,
                webhook_kind="CoreCustomWebhook",
                webhook_name="cancel-me",
                payload={"event": "cancel-during-retry-wait"},
                return_state=True,
            )
        )

        run = await wait_for_retry_wait(prefect_client, known_run_ids)
        assert failing_target.post_count == 1

        resulting_state = await PrefectClientAdapter(prefect_client).set_flow_run_state(
            flow_run_id=run.id, state=State(type=StateType.CANCELLING), force=False
        )
        assert resulting_state in {StateType.CANCELLING, StateType.CANCELLED}

        final_state = await delivery

    assert failing_target.post_count == 1, "an attempt was sent after the delivery was cancelled"
    assert final_state.type == StateType.CANCELLED

    settled = await prefect_client.read_flow_run(run.id)
    assert settled.state is not None
    assert settled.state.type == StateType.CANCELLED
