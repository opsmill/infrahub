"""Persist recomputed derived values and chain the next coalesced level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.python_target_sources import build_python_target_deriver
from infrahub.core.merge.recompute_coalescing import (
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    RecomputeChainSubmitter,
)
from infrahub.core.recompute.bulk_write import BulkRecomputeWriter
from infrahub.core.registry import registry
from infrahub.events.constants import NodeMutationOrigin
from infrahub.exceptions import BranchNotFoundError
from infrahub.workers.dependencies import get_database, get_event_service, get_workflow

if TYPE_CHECKING:
    from infrahub.core.recompute.bulk_write import AttributeValueWrite
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext


class BulkRecomputeDispatcher:
    """Persist recomputed values in one bulk write; on a coalesced pass, dispatch the next level.

    A coalesced pass stamps the write with the recompute origin and drives the next level here; a
    live pass stamps it live and lets the per-node path carry it.
    """

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        writer: BulkRecomputeWriter,
        chain: RecomputeChainSubmitter,
    ) -> None:
        self._db = db
        self._writer = writer
        self._chain = chain

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
    db = await get_database()
    writer = BulkRecomputeWriter(db=db, event_service=await get_event_service())
    chain = RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=get_workflow()),
        python_deriver=await build_python_target_deriver(db=db),
    )
    return BulkRecomputeDispatcher(db=db, writer=writer, chain=chain)
