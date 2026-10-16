from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import NodeSchema

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

_RESOURCE_POOL_KINDS = frozenset({InfrahubKind.RESOURCEPOOL, InfrahubKind.NUMBERPOOLRANGE})


def is_resource_pool_schema(schema: MainSchemaTypes) -> bool:
    """Return whether the schema is a resource pool, or the range of one, whose numbers no number pool may track."""
    if schema.kind in _RESOURCE_POOL_KINDS:
        return True
    return isinstance(schema, NodeSchema) and InfrahubKind.RESOURCEPOOL in schema.inherit_from
