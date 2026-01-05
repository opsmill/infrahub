from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.graphql import Query

from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
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
        AttributeSchema(name="number", kind="NumberPool", optional=False, read_only=True, unique=True),
    ],
)

INCIDENT = NodeSchema(
    name="Incident",
    namespace="Test",
    label="Incident",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(name="number", kind="NumberPool", optional=False, read_only=True, unique=True),
    ],
)

number_pool_allocation_query = Query(
    query={
        "InfrahubResourcePoolAllocated": {"@filters": {"pool_id": "$pool_id", "resource_id": "$pool_id"}, "count": None}
    },
    variables={"pool_id": str},
)

BRANCH2 = "branch2"


class TestAttributeNumberPoolLifecycle(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def initial_schema(self) -> SchemaRoot:
        schema = SchemaRoot(
            version="1.0",
            nodes=[INCIDENT, REQUEST],
        )
        return schema

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        prefect_test_fixture,
        initial_schema: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_load_response = await client.schema.load(
            schemas=[initial_schema.model_dump()], wait_until_converged=True
        )
        assert not schema_load_response.errors

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
