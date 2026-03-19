from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow
from prefect.logging import get_run_logger
from prefect.runtime import flow_run

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.workers.dependencies import get_database

from .cache import invalidate_webhook_cache

if TYPE_CHECKING:
    from prefect import Flow, State
    from prefect.client.schemas.objects import FlowRun


def _invalidate_webhook_headers_run_name() -> str:
    params = flow_run.parameters
    event_data = params.get("event_data")
    keyvalue_id = (event_data or {}).get("node_id", "unknown")
    return f"Invalidate webhook headers (KeyValue {keyvalue_id})"


async def _invalidate_webhook_headers_on_failure(flow: Flow, flow_run: FlowRun, state: State) -> None:  # noqa: ARG001
    log = get_run_logger()
    event_data = flow_run.parameters.get("event_data")
    keyvalue_id = event_data.get("node_id") if event_data else None
    log.error(
        "Webhook header invalidation failed: keyvalue_id=%s state_message=%s",
        keyvalue_id,
        state.message,
    )


@flow(
    name="webhook-invalidate-headers",
    flow_run_name=_invalidate_webhook_headers_run_name,
    on_failure=[_invalidate_webhook_headers_on_failure],
)
async def invalidate_webhook_headers(
    event_type: str | None = None,  # noqa: ARG001
    event_data: dict | None = None,
) -> None:
    """Resolve webhooks referencing a KeyValue node and invalidate their cache."""
    log = get_run_logger()

    keyvalue_id = (event_data or {}).get("node_id")
    if not keyvalue_id:
        log.warning("No KeyValue ID provided, skipping")
        return

    database = await get_database()

    async with database.start_session(read_only=True) as db:
        webhooks = await NodeManager.query(
            db=db,
            schema=InfrahubKind.WEBHOOK,
            filters={"headers__ids": [keyvalue_id]},
            branch_agnostic=True,
        )
        webhook_uuids = frozenset(w.id for w in webhooks)

    if webhook_uuids:
        await invalidate_webhook_cache(webhook_ids=webhook_uuids)
    else:
        log.info(f"No webhooks reference KeyValue {keyvalue_id}")
