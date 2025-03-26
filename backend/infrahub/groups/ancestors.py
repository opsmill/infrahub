from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.events.models import EventNode

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def collect_ancestors(db: InfrahubDatabase, branch: Branch, node_kind: str, node_id: str) -> list[EventNode]:
    schema = db.schema.get(name=node_kind, branch=branch, duplicate=False)

    if not isinstance(schema, NodeSchema):
        return []

    ancestors = await NodeManager.query_hierarchy(
        db=db,
        branch=branch,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        id=node_id,
        node_schema=schema,
        filters={"id": None},
    )
    return [EventNode(id=ancestor.get_id(), kind=ancestor.get_kind()) for ancestor in ancestors.values()]
