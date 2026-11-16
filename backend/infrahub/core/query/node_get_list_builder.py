from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query.index_start import IndexStart, NodeGetListIndexStartQuery
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
        query = NodeGetListQuery(
            schema=schema,
            branch=branch,
            filters=filters,
            at=at,
            limit=limit,
            offset=offset,
            partial_match=partial_match,
            branch_agnostic=branch_agnostic,
            order=order,
        )
        index_start = await self._select_index_start(node_kind=schema.kind, index_starts=query.get_index_starts())
        await query.query_init(db=self.db, index_start=index_start)
        return query

    async def _select_index_start(self, node_kind: str, index_starts: list[IndexStart]) -> IndexStart | None:
        if not index_starts:
            return None

        query = NodeGetListIndexStartQuery(node_kind=node_kind, index_starts=index_starts)
        await query.execute(db=self.db)
        return query.get_selected_index_start()
