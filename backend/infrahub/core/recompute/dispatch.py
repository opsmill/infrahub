"""Persist recomputed derived values and chain the next coalesced level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.recompute_coalescing import RecomputeChainSubmitter
from infrahub.core.recompute.bulk_write import BulkRecomputeWriter
from infrahub.core.registry import registry
from infrahub.events.constants import NodeMutationOrigin
from infrahub.exceptions import BranchNotFoundError
from infrahub.workers.dependencies import get_database, get_event_service, get_workflow
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub.core.recompute.bulk_write import AttributeValueWrite
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow


class BulkRecomputeDispatcher:
    """Persist recomputed values in one bulk write; on a coalesced pass, dispatch the next level.

    A coalesced pass stamps the write with the recompute origin and drives the next level here; a
    live pass stamps it live and lets the per-node path carry it.
    """

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        event_service: InfrahubEventService,
        workflow: InfrahubWorkflow,
        schema_branch: SchemaBranch,
    ) -> None:
        self._db = db
        self._writer = BulkRecomputeWriter(db=db, event_service=event_service)
        self._chain = RecomputeChainSubmitter(schema_branch=schema_branch, workflow=workflow)

    async def dispatch(
        self,
        *,
        writes: list[AttributeValueWrite],
        branch_name: str,
        context: EventContext,
        coalesced: bool,
        recompute_depth: int,
    ) -> None:
        if not writes:
            return

        await add_tags(db_change=True)
        try:
            branch = await registry.get_branch(db=self._db, branch=branch_name)
        except BranchNotFoundError:
            # The branch can be deleted between the reader query and here; nothing to persist then.
            return
        written = await self._writer.write(
            branch=branch,
            writes=writes,
            context=context,
            origin=NodeMutationOrigin.RECOMPUTE if coalesced else NodeMutationOrigin.LIVE,
        )
        if coalesced:
            await self._chain.submit(written=written, branch=branch_name, context=context, depth=recompute_depth)


async def build_bulk_recompute_dispatcher(schema_branch: SchemaBranch) -> BulkRecomputeDispatcher:
    """Wire a bulk recompute dispatcher from the flow-level dependencies."""
    return BulkRecomputeDispatcher(
        db=await get_database(),
        event_service=await get_event_service(),
        workflow=get_workflow(),
        schema_branch=schema_branch,
    )
