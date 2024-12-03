from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


log = get_logger(__name__)


async def get_display_labels_per_kind(
    kind: str, ids: list[str], branch_name: str, db: InfrahubDatabase, skip_missing_schema: bool = False
) -> dict[str, str]:
    """Return the display_labels of a list of nodes of a specific kind."""
    branch = await registry.get_branch(branch=branch_name, db=db)
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    try:
        fields = schema_branch.generate_fields_for_display_label(name=kind)
    except SchemaNotFoundError:
        if skip_missing_schema:
            return {}
        raise
    nodes = await NodeManager.get_many(ids=ids, fields=fields, db=db, branch=branch)
    return {node_id: await node.render_display_label(db=db) for node_id, node in nodes.items()}


async def get_display_labels(nodes: dict[str, dict[str, list[str]]], db: InfrahubDatabase) -> dict[str, dict[str, str]]:
    """Query the display_labels of a group of nodes organized per branch and per kind."""
    response: dict[str, dict[str, str]] = {}
    for branch_name, items in nodes.items():
        if branch_name not in response:
            response[branch_name] = {}
        for kind, ids in items.items():
            labels = await get_display_labels_per_kind(
                kind=kind, ids=ids, db=db, branch_name=branch_name, skip_missing_schema=True
            )
            response[branch_name].update(labels)

    return response
