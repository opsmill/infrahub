from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.graphql import Query

from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


REQUEST = NodeSchema(
    name="Request",
    namespace="Test",
    label="Request",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(
            name="number",
            kind="NumberPool",
            optional=False,
            read_only=True,
            unique=True,
            parameters=NumberPoolParameters(start_range=1, end_range=1000),
        ),
    ],
)

INCIDENT = NodeSchema(
    name="Incident",
    namespace="Test",
    label="Incident",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(
            name="number",
            kind="NumberPool",
            optional=False,
            read_only=True,
            unique=True,
            parameters=NumberPoolParameters(start_range=1, end_range=1000),
        ),
    ],
)

TICKET = NodeSchema(
    name="Ticket",
    namespace="Test",
    label="Ticket",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(name="ticket_id", kind="Number", optional=True),
    ],
)

ATTACH_TICKET_NUMBER = """
mutation AttachTicketNumber($id: String!, $value: BigInt!, $pool_id: String!) {
    TestTicketUpdate(data: { id: $id, ticket_id: { value: $value, from_pool: { id: $pool_id } } }) {
        object { ticket_id { value } }
    }
}
"""

CREATE_TICKET_FROM_POOL = """
mutation CreateTicketFromPool($title: String!, $pool_id: String!) {
    TestTicketCreate(data: { title: { value: $title }, ticket_id: { from_pool: { id: $pool_id } } }) {
        object { ticket_id { value } }
    }
}
"""

number_pool_allocation_query = Query(
    query={
        "InfrahubResourcePoolAllocated": {"@filters": {"pool_id": "$pool_id", "resource_id": "$pool_id"}, "count": None}
    },
    variables={"pool_id": str},
)

BRANCH2 = "branch2"
ATTACH_BRANCH = "attach-branch"


class TestAttributeNumberPoolLifecycle(TestInfrahubApp):
    async def _run_number_pool_validator(self, db: InfrahubDatabase) -> None:
        upserter = SchemaNumberPoolUpserter(
            db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
        )
        snps = SchemaNumberPoolSynchronizer(
            db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
        )
        await snps.run()
        graphql_registry.clear_cache()

    @pytest.fixture(scope="class")
    def initial_schema(self) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            nodes=[INCIDENT, REQUEST, TICKET],
        )

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        prefect_test_fixture: None,
        initial_schema: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_load_response = await client.schema.load(
            schemas=[initial_schema.model_dump()], wait_until_converged=True
        )
        assert not schema_load_response.errors

        await self._run_number_pool_validator(db)

        # Create incidents/requests to ensure there are some data into the database
        for idx in range(1, 4):
            incident = await client.create(kind=INCIDENT.kind, branch=default_branch.name, title=f"Incident #{idx}")
            await incident.save()

        for idx in range(1, 4):
            requests = await client.create(kind=REQUEST.kind, branch=default_branch.name, title=f"Request #{idx}")
            await requests.save()

        incidents = await client.all(kind=INCIDENT.kind, branch=default_branch.name)
        assert len(incidents) == 3
        assert sorted([incident.number.value for incident in incidents]) == [1, 2, 3]

        requests = await client.all(kind=REQUEST.kind, branch=default_branch.name)
        assert len(requests) == 3
        assert sorted([request.number.value for request in requests]) == [1, 2, 3]

    async def test_numberpool_assign_in_branch(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
        await client.branch.create(branch_name=BRANCH2, sync_with_git=False)

        for idx in range(4, 7):
            obj = await client.create(kind=REQUEST.kind, branch=BRANCH2, title=f"Request #{idx}")
            await obj.save()

        for idx in range(7, 10):
            obj = await client.create(kind=REQUEST.kind, branch=default_branch.name, title=f"Request #{idx}")
            await obj.save()

        for idx in range(4, 10):
            obj = await client.create(kind=INCIDENT.kind, branch=default_branch.name, title=f"Incident #{idx}")
            await obj.save()

        requests_main = await client.all(kind=REQUEST.kind, branch=default_branch.name)
        assert sorted([request.number.value for request in requests_main]) == [1, 2, 3, 7, 8, 9]

        requests_branch = await client.all(kind=REQUEST.kind, branch=BRANCH2)
        assert sorted([request.number.value for request in requests_branch]) == [1, 2, 3, 4, 5, 6]

        incidents = await client.all(kind=INCIDENT.kind, branch=default_branch.name)
        assert sorted([incident.number.value for incident in incidents]) == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    async def test_numberpool_branch_delete(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
        """Validate that after deleting BRANCH2, the numbers are reallocated correctly in the main branch."""
        await client.branch.delete(branch_name=BRANCH2)

        for idx in range(10, 14):
            obj = await client.create(kind=REQUEST.kind, branch=default_branch.name, title=f"Request #{idx}")
            await obj.save()

        requests_main = await client.all(kind=REQUEST.kind, branch=default_branch.name)
        assert sorted([request.number.value for request in requests_main]) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    async def test_numberpool_node_delete(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
        """Validate that after deleting BRANCH2, the numbers are reallocated correctly in the main branch."""
        incidents = await client.all(kind=INCIDENT.kind, branch=default_branch.name)
        for incident in incidents:
            await incident.delete()

        for idx in range(1, 4):
            incident = await client.create(kind=INCIDENT.kind, branch=default_branch.name, title=f"Incident #1-{idx}")
            await incident.save()

        incidents = await client.all(kind=INCIDENT.kind, branch=default_branch.name)
        assert sorted([incident.number.value for incident in incidents]) == [1, 2, 3]

    async def test_numberpool_attach_in_branch_survives_branch_delete(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
        """Attaching on a branch is global, so the pool keeps tracking the number once the branch is deleted."""
        pool = await client.create(
            kind="CoreNumberPool",
            name="ticket-pool",
            node=TICKET.kind,
            node_attribute="ticket_id",
            start_range=1,
            end_range=10,
            branch=default_branch.name,
        )
        await pool.save()
        hand_set = await client.create(kind=TICKET.kind, title="hand-set", ticket_id=1, branch=default_branch.name)
        await hand_set.save()

        await client.branch.create(branch_name=ATTACH_BRANCH, sync_with_git=False)
        attached = await client.execute_graphql(
            query=ATTACH_TICKET_NUMBER,
            variables={"id": hand_set.id, "value": 1, "pool_id": pool.id},
            branch_name=ATTACH_BRANCH,
        )
        assert attached["TestTicketUpdate"]["object"]["ticket_id"]["value"] == 1

        assert await self._allocation_count(client=client, pool_id=pool.id) == 1
        assert await self._allocate_ticket(client=client, pool_id=pool.id, title="before delete") == 2, (
            "the number attached on the branch is taken on main, with no uniqueness constraint to skip it"
        )

        await client.branch.delete(branch_name=ATTACH_BRANCH)

        assert await self._allocate_ticket(client=client, pool_id=pool.id, title="after delete") == 3
        assert await self._allocation_count(client=client, pool_id=pool.id) == 3

    async def _allocate_ticket(self, client: InfrahubClient, pool_id: str, title: str) -> int:
        created = await client.execute_graphql(
            query=CREATE_TICKET_FROM_POOL, variables={"title": title, "pool_id": pool_id}
        )
        return created["TestTicketCreate"]["object"]["ticket_id"]["value"]

    async def _allocation_count(self, client: InfrahubClient, pool_id: str) -> int:
        allocation = await client.execute_graphql(
            query=number_pool_allocation_query.render(), variables={"pool_id": pool_id}
        )
        return allocation["InfrahubResourcePoolAllocated"]["count"]
