from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import UniquenessViolationError
from tests.helpers.number_pool import register_and_provision_number_pools
from tests.helpers.schema import SNOW_INCIDENT, SNOW_TASK

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_a_number_a_schema_pool_draws_is_checked_for_uniqueness(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """The payload never names a NumberPool attribute, and the save still refuses a number another object holds."""
    await register_and_provision_number_pools(
        db=db, branch=default_branch, schema=SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT])
    )
    incident_schema = registry.schema.get_node_schema(name=SNOW_INCIDENT.kind, branch=default_branch)
    # Held outside the pool, as a number set before the attribute was handed to a pool would be.
    holding_object = await Node.init(db=db, schema=incident_schema, branch=default_branch)
    await holding_object.new(db=db, process_pools=False, title="held by hand", number=1)
    await holding_object.save(db=db)

    with pytest.raises(UniquenessViolationError) as exc_info:
        await create_node(data={"title": "drawn"}, db=db, branch=default_branch, schema=incident_schema)

    assert exc_info.value.message == "Violates uniqueness constraint 'number'"
    assert await NodeManager.query(db=db, schema=SNOW_INCIDENT.kind, filters={"title__value": "drawn"}) == []
