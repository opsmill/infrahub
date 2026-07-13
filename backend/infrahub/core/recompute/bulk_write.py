"""Persist recomputed derived values in bulk instead of one flow per value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.manager import NodeManager
from infrahub.events.constants import NodeMutationOrigin
from infrahub.events.models import EventMeta
from infrahub.events.node_action import NodeUpdatedEvent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.event import InfrahubEventService

DISPLAY_LABEL_FIELD = "display_label"
HFID_FIELD = "human_friendly_id"


@dataclass(frozen=True)
class AttributeValueWrite:
    """One recomputed derived value to persist on one node.

    ``field`` is the attribute to set: the display-label attribute, the human-friendly-id
    attribute, or a computed attribute's own name. ``value`` is a list of parts for the
    human-friendly id and a string for the others.
    """

    node_id: str
    field: str
    value: str | list[str] | None


@dataclass(frozen=True)
class WrittenNode:
    """A node whose derived values were persisted, and the fields that were written.

    Returned so the caller can chain: these writes become the change set of the next coalesced
    recompute level, reaching values that read them.
    """

    node_id: str
    kind: str
    fields: tuple[str, ...]


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def _apply(node: Node, write: AttributeValueWrite) -> None:
    if write.field == DISPLAY_LABEL_FIELD:
        await node.set_display_label(value=cast("str | None", write.value))
    elif write.field == HFID_FIELD:
        await node.set_human_friendly_id(value=cast("list[str] | None", write.value))
    else:
        getattr(node, write.field).value = write.value


class BulkRecomputeWriter:
    """Persist recomputed derived values for many nodes without a per-value flow fan-out.

    Writes are grouped by node so a node reached by several families is saved once, applied in
    bounded transactions to keep the lock footprint contained, then followed by one live update
    event per node so values that read them still recompute.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        event_service: InfrahubEventService,
        transaction_chunk_size: int = 100,
    ) -> None:
        self.db = db
        self.event_service = event_service
        self.transaction_chunk_size = transaction_chunk_size

    async def write(
        self,
        *,
        branch: Branch,
        writes: list[AttributeValueWrite],
        context: EventContext,
        origin: NodeMutationOrigin = NodeMutationOrigin.LIVE,
    ) -> list[WrittenNode]:
        """Persist ``writes`` and return the nodes written, so the caller can chain the next level.

        ``origin`` stamps the update event: keep the default live origin so the per-node recompute
        automations chain the next level, or pass the recompute origin when the caller drives that
        next level itself as one coalesced pass.
        """
        writes_by_node: dict[str, list[AttributeValueWrite]] = {}
        for item in writes:
            writes_by_node.setdefault(item.node_id, []).append(item)

        fields_to_load = {item.field: None for item in writes}
        user_id = context.account_id or SYSTEM_USER_ID
        written: list[WrittenNode] = []
        async with self.db.start_session() as session:
            for chunk in _chunks(list(writes_by_node), self.transaction_chunk_size):
                nodes = await NodeManager.get_many(db=session, ids=chunk, fields=fields_to_load, branch=branch)
                saved: list[tuple[Node, list[str]]] = []
                async with session.start_transaction() as dbt:
                    for node_id in chunk:
                        node = nodes.get(node_id)
                        if node is None:
                            continue
                        fields = sorted({item.field for item in writes_by_node[node_id]})
                        for item in writes_by_node[node_id]:
                            await _apply(node=node, write=item)
                        await node.save(db=dbt, user_id=user_id, fields=fields)
                        # A recompute can render a value identical to the stored one; skip the event and
                        # the chained write for a no-op save so it does not fan out.
                        if node.node_changelog.has_changes:
                            saved.append((node, fields))
                for node, fields in saved:
                    await self._emit(node=node, fields=fields, branch=branch, context=context, origin=origin)
                    written.append(WrittenNode(node_id=node.get_id(), kind=node.get_kind(), fields=tuple(fields)))
        return written

    async def _emit(
        self,
        *,
        node: Node,
        fields: list[str],
        branch: Branch,
        context: EventContext,
        origin: NodeMutationOrigin,
    ) -> None:
        meta = EventMeta.from_context(context=context, branch=branch)
        meta.origin = origin
        event = NodeUpdatedEvent(
            kind=node.get_kind(),
            node_id=node.get_id(),
            changelog=node.node_changelog,
            fields=fields,
            meta=meta,
        )
        await self.event_service.send(event=event)
