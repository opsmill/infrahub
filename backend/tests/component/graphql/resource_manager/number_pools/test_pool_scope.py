from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.number_pool import SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema

from .helpers import bounds_input, execute

CREATE_SCOPED_POOL = """
mutation CreateScopedPool($data: CoreNumberPoolCreateInput!) {
  CoreNumberPoolCreate(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""

UPDATE_SCOPED_POOL = """
mutation UpdateScopedPool($data: CoreNumberPoolUpdateInput!) {
  CoreNumberPoolUpdate(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""

QUERY_POOL_SCOPE = """
query PoolScope($id: ID!) {
  CoreNumberPool(ids: [$id]) {
    edges { node { allocation_scope { value } } }
  }
}
"""


def device_pool_input(name: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {
        "name": {"value": name},
        "node": {"value": "ScopeDevice"},
        "node_attribute": {"value": "number"},
    } | bounds_input(start=1, end=100)
    if scope is not None:
        data["allocation_scope"] = scope
    return data


async def create_device_pool(
    db: InfrahubDatabase, branch: Branch, name: str, scope: dict[str, Any] | None = None
) -> dict[str, Any]:
    result = await execute(
        db=db, branch=branch, source=CREATE_SCOPED_POOL, variables={"data": device_pool_input(name=name, scope=scope)}
    )
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPoolCreate"]["object"]


async def read_scope(db: InfrahubDatabase, branch: Branch, pool_id: str) -> list[str] | None:
    result = await execute(db=db, branch=branch, source=QUERY_POOL_SCOPE, variables={"id": pool_id})
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPool"]["edges"][0]["node"]["allocation_scope"]["value"]


class TestNumberPoolAllocationScope:
    """The allocation scope is stored on the pool and read back as written.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def device_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA)
        default_branch_scope_class.update_schema_hash()

    async def test_create_with_scope_reads_it_back(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="scoped-pool", scope={"value": ["site"]}
        )

        assert pool["allocation_scope"]["value"] == ["site"]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site"]

    async def test_create_without_scope_reads_null(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(db=db, branch=default_branch_scope_class, name="unscoped-pool")

        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None

    async def test_update_with_null_clears_the_scope(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="cleared-pool", scope={"value": ["site"]}
        )

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_SCOPED_POOL,
            variables={"data": {"id": pool["id"], "allocation_scope": {"value": None}}},
        )

        assert not result.errors
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None
