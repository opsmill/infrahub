from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot

from .car import CAR
from .child import CHILD
from .color import COLOR
from .location import CONTINENT, COUNTRY, LOCATION, SITE
from .manufacturer import MANUFACTURER
from .person import PERSON
from .thing import THING
from .ticket import TICKET
from .tshirt import TSHIRT
from .widget import WIDGET

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


CAR_SCHEMA = SchemaRoot(nodes=[CAR, MANUFACTURER, PERSON])
LOCATION_SCHEMA = SchemaRoot(generics=[LOCATION], nodes=[CONTINENT, COUNTRY, SITE])


async def load_schema(
    db: InfrahubDatabase, schema: SchemaRoot, branch_name: str | None = None, update_db: bool = False
) -> None:
    branch_name = branch_name or registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=branch_name)
    registry.schema.register_schema(schema=schema, branch=branch_name)
    await registry.schema.update_schema_branch(
        schema=branch_schema.duplicate(), db=db, branch=branch_name, update_db=update_db
    )
    registry.get_branch_from_registry(branch_name).update_schema_hash()


__all__ = [
    "CAR",
    "CAR_SCHEMA",
    "CHILD",
    "COLOR",
    "CONTINENT",
    "COUNTRY",
    "LOCATION",
    "LOCATION_SCHEMA",
    "MANUFACTURER",
    "PERSON",
    "SITE",
    "THING",
    "TICKET",
    "TSHIRT",
    "WIDGET",
]
