from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.pools.attribute_pool_applier import AttributePoolApplier
from infrahub.pools.division_reader import NodeNumberPoolDivisionReader
from infrahub.pools.intent import FromPoolIntentResolver
from infrahub.pools.number_pool_attribute_allocator import NumberPoolAttributeAllocator
from infrahub.pools.number_pool_lookup import NumberPoolLookup
from infrahub.pools.scope import AllocationScopeResolver

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.profiles.node_applier import NodeProfilesApplier


def build_attribute_pool_applier(
    db: InfrahubDatabase, schema_branch: SchemaBranch, profiles_applier: NodeProfilesApplier
) -> AttributePoolApplier:
    """Build the component that gives attributes their numbers from number pools, reading and writing through `db`.

    `schema_branch` is the schema of the branch the write runs on, where a scoped pool's division is read, and
    `profiles_applier` gives the node the profile values it will hold once saved before that division is read.
    """
    return AttributePoolApplier(
        pool_finder=NumberPoolLookup(db=db, node_manager=registry.manager),
        number_allocator=NumberPoolAttributeAllocator(db=db),
        intent_resolver=FromPoolIntentResolver(),
        division_reader=NodeNumberPoolDivisionReader(
            db=db,
            scope_resolver=AllocationScopeResolver(schema_branch=schema_branch),
            profiles_applier=profiles_applier,
        ),
    )
