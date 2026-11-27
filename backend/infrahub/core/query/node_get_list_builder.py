from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.ownership.constants import SOURCES_IDS_FILTER
from infrahub.core.ownership.filter import has_owner_filter
from infrahub.core.query.index_start import IndexStart, NodeGetListIndexStartQuery, get_index_starts
from infrahub.core.query.node import NodeGetListQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.order import OrderModel
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class NodeGetListQueryBuilder:
    """Build the list query of a kind, entered from the filter whose indexed vertices have the fewest edges.

    The count that picks the start runs here, before the text of the list query is built.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def build(
        self,
        schema: MainSchemaTypes,
        branch: Branch,
        filters: dict[str, Any] | None = None,
        at: Timestamp | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        partial_match: bool = False,
        branch_agnostic: bool = False,
        order: OrderModel | None = None,
    ) -> NodeGetListQuery:
        index_start = None
        # The owner and source filters bind the nodes before the start, and an index start would bind them again.
        if not has_owner_filter(filters=filters) and (filters or {}).get(SOURCES_IDS_FILTER) is None:
            index_start = await self._select_index_start(
                node_kind=schema.kind,
                index_starts=get_index_starts(schema=schema, filters=filters, partial_match=partial_match),
            )
        return await NodeGetListQuery.init(
            db=self.db,
            schema=schema,
            branch=branch,
            filters=filters,
            at=at,
            limit=limit,
            offset=offset,
            partial_match=partial_match,
            branch_agnostic=branch_agnostic,
            order=order,
            index_start=index_start,
        )

    async def _select_index_start(self, node_kind: str, index_starts: list[IndexStart]) -> IndexStart | None:
        if not index_starts:
            return None

        query = NodeGetListIndexStartQuery(node_kind=node_kind, index_starts=index_starts)
        await query.execute(db=self.db)
        return query.get_selected_index_start()
