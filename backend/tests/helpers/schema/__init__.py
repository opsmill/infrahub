from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import core_registry
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.registry import registry as graphql_registry

from .car import CAR
from .child import CHILD
from .color import COLOR
from .device import DEVICE, INTERFACE, INTERFACE_HOLDER, PHYSICAL_INTERFACE, SFP, VIRTUAL_INTERFACE
from .location import CONTINENT, COUNTRY, LOCATION, SITE
from .manufacturer import MANUFACTURER
from .person import PERSON
from .snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK
from .thing import THING
from .ticket import TICKET
from .tshirt import TSHIRT
from .widget import WIDGET

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


CAR_SCHEMA = SchemaRoot(nodes=[CAR, MANUFACTURER, PERSON])
DEVICE_SCHEMA = SchemaRoot(
    generics=[INTERFACE, INTERFACE_HOLDER], nodes=[DEVICE, PHYSICAL_INTERFACE, VIRTUAL_INTERFACE, SFP]
)
LOCATION_SCHEMA = SchemaRoot(generics=[LOCATION], nodes=[CONTINENT, COUNTRY, SITE])
SNOW_TICKET_SCHEMA = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])


async def load_schema(
    db: InfrahubDatabase, schema: SchemaRoot, branch_name: str | None = None, update_db: bool = False
) -> None:
    branch_name = branch_name or core_registry.default_branch
    branch_schema = core_registry.schema.get_schema_branch(name=branch_name)
    core_registry.schema.register_schema(schema=schema, branch=branch_name)
    await core_registry.schema.update_schema_branch(
        schema=branch_schema.duplicate(), db=db, branch=branch_name, update_db=update_db
    )
    branch = core_registry.get_branch_from_registry(branch_name)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


__all__ = [
    "CAR",
    "CAR_SCHEMA",
    "CHILD",
    "COLOR",
    "CONTINENT",
    "COUNTRY",
    "DEVICE",
    "DEVICE_SCHEMA",
    "INTERFACE",
    "INTERFACE_HOLDER",
    "LOCATION",
    "LOCATION_SCHEMA",
    "MANUFACTURER",
    "PERSON",
    "PHYSICAL_INTERFACE",
    "SFP",
    "SITE",
    "THING",
    "TICKET",
    "TSHIRT",
    "VIRTUAL_INTERFACE",
    "WIDGET",
]
