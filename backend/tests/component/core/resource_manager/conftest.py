from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SERIAL_POOL_START = 7001
SERIAL_POOL_END = 7010
SERIAL_ATTRIBUTE_NAME = "serial"


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    """The widget kind with its pooled `serial` attribute branch-agnostic."""
    return registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


@pytest.fixture
async def serial_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> CoreNumberPool:
    """Bound to the kind and attribute by name, so it fits whichever branch support the test registers."""
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name="serial-pool",
        node=WIDGET_KIND,
        node_attribute=SERIAL_ATTRIBUTE_NAME,
        start_range=SERIAL_POOL_START,
        end_range=SERIAL_POOL_END,
    )
    await pool.save(db=db)
    return pool
