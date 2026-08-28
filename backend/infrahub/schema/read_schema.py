from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.schema.generated.read import BaseNodeSchemaRead

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


def build_read_schema[TApiSchema: BaseNodeSchemaRead](model: type[TApiSchema], schema: MainSchemaTypes) -> TApiSchema:
    """Project an internal schema onto the read model published for its kind."""
    data = schema.model_dump()
    data["relationships"] = [
        relationship.model_dump() for relationship in schema.relationships if not relationship.internal_peer
    ]
    data["hash"] = schema.get_hash()
    return model(**data)
