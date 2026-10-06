from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.pools.attribute_pool_applier import AttributePoolApplier
from infrahub.pools.number_pool_attribute_allocator import NumberPoolAttributeAllocator
from infrahub.pools.number_pool_lookup import NumberPoolLookup

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def build_attribute_pool_applier(db: InfrahubDatabase) -> AttributePoolApplier:
    """Build the component that gives attributes their numbers from number pools, reading and writing through `db`."""
    return AttributePoolApplier(
        pool_finder=NumberPoolLookup(db=db, node_manager=registry.manager),
        number_allocator=NumberPoolAttributeAllocator(db=db),
    )
