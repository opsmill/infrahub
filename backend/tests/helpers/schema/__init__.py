from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.registry import registry as graphql_registry

from .car import CAR
from .child import CHILD
from .color import COLOR
from .device import DEVICE, INTERFACE, INTERFACE_HOLDER, PHYSICAL_INTERFACE, SFP, VIRTUAL_INTERFACE
from .file_contract import FILE_CONTRACT
from .location import CONTINENT, COUNTRY, LOCATION, SITE
from .manufacturer import MANUFACTURER
from .person import PERSON
from .recompute import CASCADE_NODE, CYCLE_A, CYCLE_B
from .snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK
from .tag import TAG
from .thing import THING
from .ticket import TICKET
from .tshirt import TSHIRT
from .widget import WIDGET

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.database import InfrahubDatabase


CAR_SCHEMA = SchemaRoot(nodes=[CAR, MANUFACTURER, PERSON, TAG])
DEVICE_SCHEMA = SchemaRoot(
    generics=[INTERFACE, INTERFACE_HOLDER], nodes=[DEVICE, PHYSICAL_INTERFACE, VIRTUAL_INTERFACE, SFP]
)
LOCATION_SCHEMA = SchemaRoot(generics=[LOCATION], nodes=[CONTINENT, COUNTRY, SITE])
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
    await registry.schema.update_schema_branch(
        schema=branch_schema.duplicate(), db=db, branch=branch_name, limit=limit, update_db=update_db
    )
    branch = registry.get_branch_from_registry(branch_name)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


async def apply_schema_update(db: InfrahubDatabase, schema: SchemaRoot, branch_name: str | None = None) -> None:
    """Apply a schema change the way the schema-load API does: by diff against the branch's current schema.

    Unlike `load_schema`, which upserts every kind it is given, this honours the two things only a
    diff can express: a kind or element with ``state: absent`` is removed, and an element carrying the
    ``id`` of an existing one is renamed rather than replaced. Migrations are not run.
    """
    branch_name = branch_name or registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=branch_name)
    candidate = branch_schema.duplicate()
    candidate.load_schema(schema=schema)
    candidate.process()
    diff = branch_schema.diff(other=candidate)
    candidate.validate_node_deletions(diff=diff)
    await registry.schema.update_schema_branch(schema=candidate, db=db, branch=branch_name, diff=diff, update_db=True)
    branch = registry.get_branch_from_registry(branch_name)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


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
    "SFP",
    "SITE",
    "TAG",
    "THING",
    "TICKET",
    "TSHIRT",
    "VIRTUAL_INTERFACE",
    "WIDGET",
]
