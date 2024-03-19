from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot

from .car import CAR
from .manufacturer import MANUFACTURER
from .person import PERSON

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


CAR_SCHEMA = SchemaRoot(nodes=[CAR, MANUFACTURER, PERSON])


async def load_schema(db: InfrahubDatabase, schema: SchemaRoot) -> None:
    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()
    tmp_schema.load_schema(schema=schema)
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


__all__ = ["CAR", "MANUFACTURER", "PERSON", "CAR_SCHEMA"]
