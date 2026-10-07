import pytest

from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import TICKET, load_schema

from .helpers import execute, load_pool, ticket_pool_input

CREATE_NUMBER_POOL_WITH_SCOPE = """
mutation CreateNumberPool($data: CoreNumberPoolCreateInput!) {
  CoreNumberPoolCreate(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""


CLEAR_NUMBER_POOL_SCOPE = """
mutation ClearNumberPoolScope($data: CoreNumberPoolUpdateInput!) {
  CoreNumberPoolUpdate(data: $data) {
    ok
    object { allocation_scope { value } }
  }
}
"""


BOUNDS = {"start_range": {"value": 1}, "end_range": {"value": 100}}


class TestNumberPoolAllocationScope:
    """The scope round-trips through the pool mutations.

    An unscoped pool reads back as null or an empty list, and the two mean the same thing.
    """

    @pytest.fixture(scope="class")
    async def ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        default_branch_scope_class.update_schema_hash()

    async def test_create_with_scope_reads_it_back(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_SCOPE,
            variables={
                "data": ticket_pool_input(name="scoped-pool", bounds=BOUNDS)
                | {"allocation_scope": {"value": ["title"]}}
            },
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolCreate"]["object"]
        assert created["allocation_scope"]["value"] == ["title"]

        pool = await load_pool(db=db, pool_id=created["id"])
        assert pool.allocation_scope.value == ["title"]

    async def test_create_without_scope_reads_back_null(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_SCOPE,
            variables={"data": ticket_pool_input(name="unscoped-pool", bounds=BOUNDS)},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolCreate"]["object"]
        assert created["allocation_scope"]["value"] is None

        pool = await load_pool(db=db, pool_id=created["id"])
        assert pool.allocation_scope.value is None

    async def test_update_with_null_clears_the_scope(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        created = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_SCOPE,
            variables={
                "data": ticket_pool_input(name="pool-to-unscope", bounds=BOUNDS)
                | {"allocation_scope": {"value": ["title"]}}
            },
        )
        assert not created.errors
        assert created.data
        pool_id = created.data["CoreNumberPoolCreate"]["object"]["id"]

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CLEAR_NUMBER_POOL_SCOPE,
            variables={"data": {"id": pool_id, "allocation_scope": {"value": None}}},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["object"]["allocation_scope"]["value"] is None

        pool = await load_pool(db=db, pool_id=pool_id)
        assert pool.allocation_scope.value is None
