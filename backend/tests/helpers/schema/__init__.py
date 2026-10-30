from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.models import SchemaBranchDiff
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.registry import registry as graphql_registry
from tests.helpers.planner_statistics import refresh_planner_statistics

from .car import CAR
from .child import CHILD
from .color import COLOR
from .device import DEVICE, INTERFACE, INTERFACE_HOLDER, PHYSICAL_INTERFACE, SFP, VIRTUAL_INTERFACE
from .file_contract import FILE_CONTRACT
from .location import CONTINENT, COUNTRY, LOCATION, SITE
from .manufacturer import MANUFACTURER
from .person import PERSON
from .rack import CARD, POWER_SLOT, RACK, SLOT
from .recompute import CASCADE_NODE, CYCLE_A, CYCLE_B
from .snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK
from .tag import TAG
from .thing import THING
from .ticket import TICKET
from .tshirt import TSHIRT
from .widget import WIDGET

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


CAR_SCHEMA = SchemaRoot(nodes=[CAR, MANUFACTURER, PERSON, TAG])
DEVICE_SCHEMA = SchemaRoot(
    generics=[INTERFACE, INTERFACE_HOLDER], nodes=[DEVICE, PHYSICAL_INTERFACE, VIRTUAL_INTERFACE, SFP]
)
LOCATION_SCHEMA = SchemaRoot(generics=[LOCATION], nodes=[CONTINENT, COUNTRY, SITE])
RACK_SCHEMA = SchemaRoot(generics=[SLOT], nodes=[RACK, POWER_SLOT, CARD, TAG])
SNOW_TICKET_SCHEMA = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
CASCADE_SCHEMA = SchemaRoot(nodes=[CASCADE_NODE])
CYCLE_SCHEMA = SchemaRoot(nodes=[CYCLE_A, CYCLE_B])


async def load_schema(
    db: InfrahubDatabase,
    schema: SchemaRoot,
    branch_name: str | None = None,
    update_db: bool = False,
    limit: list[str] | None = None,
) -> None:
    branch_name = branch_name or registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=branch_name)
    registry.schema.register_schema(schema=schema, branch=branch_name)
    if update_db:
        await _write_and_read_back_schema(db=db, schema=branch_schema.duplicate(), branch_name=branch_name, limit=limit)
    else:
        await registry.schema.update_schema_branch(
            schema=branch_schema.duplicate(), db=db, branch=branch_name, update_db=False
        )
    branch = registry.get_branch_from_registry(branch_name)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


async def _write_and_read_back_schema(
    db: InfrahubDatabase, schema: SchemaBranch, branch_name: str, limit: list[str] | None
) -> None:
    """Persist the schema and install the copy read back from the database, as a schema update that writes does.

    The planner statistics are refreshed between the write and the read, because the read loads
    every schema node the write has just created.
    """
    branch = await registry.get_branch(db=db, branch=branch_name)
    at = Timestamp()
    await registry.schema.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit, at=at)
    await refresh_planner_statistics(db=db)

    schema_diff = None
    if limit:
        schema_diff = SchemaBranchDiff(
            added_nodes=[name for name in schema.nodes if name in limit],
            added_generics=[name for name in schema.generics if name in limit],
        )
    updated_schema = await registry.schema.load_schema_from_db(
        db=db, branch=branch, schema=schema, schema_diff=schema_diff, at=at
    )
    registry.schema.set_schema_branch(name=branch.name, schema=updated_schema)


test_generics: list[GenericSchema] = [SNOW_TASK, INTERFACE, INTERFACE_HOLDER]
test_nodes: list[NodeSchema] = [
    CAR,
    MANUFACTURER,
    PERSON,
    SNOW_INCIDENT,
    SNOW_REQUEST,
    DEVICE,
    PHYSICAL_INTERFACE,
    VIRTUAL_INTERFACE,
    SFP,
]

test_models: dict[str, Any] = {
    "generics": [item.to_dict() for item in test_generics],
    "nodes": [item.to_dict() for item in test_nodes],
}


__all__ = [
    "CAR",
    "CARD",
    "CAR_SCHEMA",
    "CASCADE_NODE",
    "CASCADE_SCHEMA",
    "CHILD",
    "COLOR",
    "CONTINENT",
    "COUNTRY",
    "CYCLE_A",
    "CYCLE_B",
    "CYCLE_SCHEMA",
    "DEVICE",
    "DEVICE_SCHEMA",
    "FILE_CONTRACT",
    "INTERFACE",
    "INTERFACE_HOLDER",
    "LOCATION",
    "LOCATION_SCHEMA",
    "MANUFACTURER",
    "PERSON",
    "PHYSICAL_INTERFACE",
    "POWER_SLOT",
    "RACK",
    "RACK_SCHEMA",
    "SFP",
    "SITE",
    "SLOT",
    "TAG",
    "THING",
    "TICKET",
    "TSHIRT",
    "VIRTUAL_INTERFACE",
    "WIDGET",
]
