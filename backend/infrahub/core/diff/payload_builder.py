from __future__ import annotations

from itertools import batched
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeListGetDisplayLabelQuery
from infrahub.core.registry import registry
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.database import InfrahubDatabase


log = get_logger(__name__)


async def get_stored_display_labels(db: InfrahubDatabase, branch_name: str, node_ids: Iterable[str]) -> dict[str, str]:
    """Return the display labels stored on these nodes, keyed by node id, as seen from the branch.

    Reading the stored label costs one query per batch of ids, where computing it through
    ``get_display_labels_per_kind`` builds a full node object per id. A node is missing from the
    result when it is not active on the branch or when it has no display label stored yet.
    """
    branch = await registry.get_branch(branch=branch_name, db=db)
    display_label_map: dict[str, str] = {}
    for ids_batch in batched(node_ids, config.SETTINGS.database.query_size_limit):
        query = await NodeListGetDisplayLabelQuery.init(db=db, branch=branch, ids=list(ids_batch))
        await query.execute(db=db)
        display_label_map.update(query.get_display_label_map())
    return display_label_map


async def get_display_labels_per_kind(
    kind: str, ids: list[str], branch_name: str, db: InfrahubDatabase, skip_missing_schema: bool = False
) -> dict[str, str]:
    """Return the display_labels of a list of nodes of a specific kind.

    Raises:
        SchemaNotFoundError: When the schema for `kind` cannot be found and `skip_missing_schema` is False.

    """
    branch = await registry.get_branch(branch=branch_name, db=db)
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    try:
        fields = schema_branch.generate_fields_for_display_label(name=kind)
    except SchemaNotFoundError:
        if skip_missing_schema:
            return {}
        raise
    display_label_map: dict[str, str] = {}
    offset = 0
    limit = config.SETTINGS.database.query_size_limit
    while True:
        limited_ids = ids[offset : offset + limit]
        if not limited_ids:
            break
        node_map = await NodeManager.get_many(ids=limited_ids, fields=fields, db=db, branch=branch)
        for node_id, node in node_map.items():
            display_label_map[node_id] = await node.get_display_label(db=db)
        offset += limit
    return display_label_map


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
