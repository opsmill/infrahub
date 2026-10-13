from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.pools.number_pool_allocations_reader import NumberPoolAllocationsReader
from infrahub.pools.number_pool_divisions_reader import NumberPoolDivisionsReader
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_space import SchemaAttributeDomains
from infrahub.pools.number_pool_usage_nodes import HoldingObjectReader, PeerSummaryReader
from infrahub.pools.number_pool_usage_state import NumberPoolStateLoader
from infrahub.pools.number_pool_utilization_reader import NumberPoolUtilizationReader
from infrahub.pools.scope import AllocationScopeResolver

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def build_number_pool_state_loader(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch, repository: NumberPoolRepository
) -> NumberPoolStateLoader:
    return NumberPoolStateLoader(
        db=db,
        branch=branch,
        repository=repository,
        scope_resolver=AllocationScopeResolver(schema_branch=schema_branch),
        domains=SchemaAttributeDomains(schema=db.schema, branch=branch),
    )


def build_number_pool_utilization_reader(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch
) -> NumberPoolUtilizationReader:
    return NumberPoolUtilizationReader(
        db=db,
        branch=branch,
        loader=build_number_pool_state_loader(
            db=db, branch=branch, schema_branch=schema_branch, repository=NumberPoolRepository(db=db)
        ),
    )


def build_number_pool_divisions_reader(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch
) -> NumberPoolDivisionsReader:
    repository = NumberPoolRepository(db=db)
    return NumberPoolDivisionsReader(
        branch=branch,
        loader=build_number_pool_state_loader(db=db, branch=branch, schema_branch=schema_branch, repository=repository),
        repository=repository,
        peer_reader=PeerSummaryReader(db=db, branch=branch),
    )


def build_number_pool_allocations_reader(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch
) -> NumberPoolAllocationsReader:
    return NumberPoolAllocationsReader(
        db=db,
        branch=branch,
        loader=build_number_pool_state_loader(
            db=db, branch=branch, schema_branch=schema_branch, repository=NumberPoolRepository(db=db)
        ),
        holder_reader=HoldingObjectReader(db=db),
    )
