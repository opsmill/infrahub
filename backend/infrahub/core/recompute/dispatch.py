"""Persist recomputed derived values and chain the next coalesced level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.recompute_coalescing import submit_recompute_chain
from infrahub.core.recompute.bulk_write import BulkRecomputeWriter
from infrahub.core.registry import registry
from infrahub.events.constants import NodeMutationOrigin
from infrahub.workers.dependencies import get_database, get_event_service, get_workflow
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub.core.recompute.bulk_write import AttributeValueWrite
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.events.models import EventContext


async def persist_and_chain(
    *,
    writes: list[AttributeValueWrite],
    schema_branch: SchemaBranch,
    branch_name: str,
    context: EventContext,
    coalesced: bool,
    recompute_depth: int,
) -> None:
    """Persist recomputed values in one bulk write; on a coalesced pass, dispatch the next level.

    An empty write set is a no-op. A coalesced pass stamps the write with the recompute origin and
    drives the next level here; a live pass stamps it live and lets the per-node path carry it.
    """
    if not writes:
        return

    await add_tags(nodes=sorted({item.node_id for item in writes}), db_change=True)
    db = await get_database()
    branch = await registry.get_branch(db=db, branch=branch_name)
    writer = BulkRecomputeWriter(db=db, event_service=await get_event_service())
    written = await writer.write(
        branch=branch,
        writes=writes,
        context=context,
        origin=NodeMutationOrigin.RECOMPUTE if coalesced else NodeMutationOrigin.LIVE,
    )
    if coalesced:
        await submit_recompute_chain(
            written=written,
            schema_branch=schema_branch,
            branch=branch_name,
            workflow=get_workflow(),
            context=context,
            depth=recompute_depth,
        )
