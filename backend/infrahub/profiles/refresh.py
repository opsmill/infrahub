"""Re-apply the assigned profiles to nodes and templates directly against the database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.recompute.bulk_write import WrittenNode, send_node_updated_event
from infrahub.database import retry_db_transaction
from infrahub.events.constants import NodeMutationOrigin
from infrahub.exceptions import DatabaseError, QueryTimeoutError
from infrahub.log import get_run_logger
from infrahub.utilities.chunks import chunked

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.merge.recompute_coalescing import RecomputeChainSubmitter
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.event import InfrahubEventService

    from .node_applier import ChunkProfilesApplier


@dataclass(frozen=True)
class AppliedNode:
    node: Node
    fields: tuple[str, ...]
    """The fields that the profiles changed, and the derived values of the node that the save recomputed."""


@dataclass(frozen=True)
class AppliedChunk:
    applied: list[AppliedNode]
    failed_node_ids: list[str]


class NodeProfilesRefresher:
    """Re-apply the assigned profiles to nodes and templates, then recompute the values that read them.

    Each chunk of nodes is applied in one transaction. When a chunk fails, its nodes are applied again
    one by one, so that only the nodes that fail are skipped. The writes carry the recompute origin, and
    their readers on other nodes are recomputed in one coalesced pass.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        event_service: InfrahubEventService,
        chain: RecomputeChainSubmitter,
        applier_class: type[ChunkProfilesApplier],
        transaction_chunk_size: int = 100,
    ) -> None:
        self.db = db
        self.event_service = event_service
        self.chain = chain
        self.applier_class = applier_class
        self.transaction_chunk_size = transaction_chunk_size

    async def refresh(self, branch: Branch, node_ids: list[str], context: EventContext) -> list[str]:
        """Refresh the profiles of ``node_ids`` and return the ids of the nodes that could not be refreshed.

        Raises:
            DatabaseError: If the database cannot be reached.
            QueryTimeoutError: If a query of the refresh times out.

        """
        user_id = context.account_id or SYSTEM_USER_ID
        written: list[WrittenNode] = []
        failed_node_ids: list[str] = []
        try:
            async with self.db.start_session() as session:
                for chunk in chunked(node_ids, self.transaction_chunk_size):
                    result = await self._apply_isolated(db=session, branch=branch, node_ids=chunk, user_id=user_id)
                    failed_node_ids.extend(result.failed_node_ids)
                    # Record the committed chunk before its events, so a failed send still recomputes its readers.
                    written.extend(
                        WrittenNode(node_id=applied.node.get_id(), kind=applied.node.get_kind(), fields=applied.fields)
                        for applied in result.applied
                    )
                    for applied in result.applied:
                        await send_node_updated_event(
                            event_service=self.event_service,
                            node=applied.node,
                            fields=list(applied.fields),
                            branch=branch,
                            context=context,
                            origin=NodeMutationOrigin.RECOMPUTE,
                        )
        finally:
            # A rerun sees no change on committed chunks, so their readers recompute even when a later chunk fails.
            await self.chain.submit(written=written, branch=branch.name, context=context, depth=0)
        return failed_node_ids

    async def _apply_isolated(
        self, db: InfrahubDatabase, branch: Branch, node_ids: list[str], user_id: str
    ) -> AppliedChunk:
        log = get_run_logger()
        try:
            return await self._apply_in_transaction(db=db, branch=branch, node_ids=node_ids, user_id=user_id)
        except (DatabaseError, QueryTimeoutError):
            raise
        # The transaction rolled back, so the chunk can be applied again without the nodes that fail.
        except Exception as exc:
            if len(node_ids) == 1:
                log.warning(f"Skipping the profile refresh of {node_ids[0]}: {exc}", exc_info=True)
                return AppliedChunk(applied=[], failed_node_ids=list(node_ids))
            log.info(f"Refreshing the profiles of {len(node_ids)} nodes one by one, after their chunk failed: {exc}")

        applied: list[AppliedNode] = []
        failed_node_ids: list[str] = []
        for node_id in node_ids:
            result = await self._apply_isolated(db=db, branch=branch, node_ids=[node_id], user_id=user_id)
            applied.extend(result.applied)
            failed_node_ids.extend(result.failed_node_ids)
        return AppliedChunk(applied=applied, failed_node_ids=failed_node_ids)

    @retry_db_transaction(name="profile_refresh")
    async def _apply_in_transaction(
        self, db: InfrahubDatabase, branch: Branch, node_ids: list[str], user_id: str
    ) -> AppliedChunk:
        applied: list[AppliedNode] = []
        async with db.start_transaction() as dbt:
            # Loaded inside the retried transaction, so that a retry never starts from nodes a failed attempt changed.
            nodes = await NodeManager.get_many(
                db=dbt, ids=node_ids, branch=branch, include_metadata=MetadataOptions.SOURCE
            )
            applier = self.applier_class(db=dbt, branch=branch)
            await applier.load_profile_data(nodes=list(nodes.values()))
            for node in nodes.values():
                profile_fields = await applier.apply_profiles(node=node)
                if not profile_fields:
                    continue
                await node.save(db=dbt, user_id=user_id, fields=profile_fields)
                # The applier writes relationships itself, so the changelog can miss one that a profile no longer sets.
                fields = tuple(sorted(set(profile_fields) | set(node.node_changelog.updated_fields)))
                applied.append(AppliedNode(node=node, fields=fields))

        missing_node_ids = [node_id for node_id in node_ids if node_id not in nodes]
        if missing_node_ids:
            get_run_logger().warning(
                f"Skipping the profile refresh of {', '.join(missing_node_ids)}: not found on branch {branch.name}"
            )
        return AppliedChunk(applied=applied, failed_node_ids=missing_node_ids)
