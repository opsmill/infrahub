from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import NumberPoolType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger
from infrahub.pools.tasks import SchemaNumberPoolValidator
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

log = get_logger()
SERVER_KIND = "TestingServer"


class TestNumberPoolSingleInstanceAcrossBranches(TestInfrahubApp):
    """Test that NumberPool attribute creates a single CoreNumberPool instance shared across branches.

    This test verifies:
    1. Loading the same schema on default and a user branch results in only one CoreNumberPool
    2. Instances created on different branches get unique values from the shared pool
    """

    @pytest.fixture(scope="class")
    def schema_with_numberpool(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Server",
                    "namespace": "Testing",
                    "include_in_menu": True,
                    "label": "Server",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {
                            "name": "rack_unit",
                            "kind": "NumberPool",
                            "optional": False,
                            "read_only": True,
                            "parameters": {"start_range": 1, "end_range": 42},
                        },
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    async def setup_branch(
        self,
        db: InfrahubDatabase,
    ) -> Branch:
        branch = await create_branch(db=db, branch_name="numberpool-single-instance-branch")
        return branch

    @pytest.fixture(scope="class")
    async def load_schema_on_default(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        schema_with_numberpool: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_with_numberpool], branch=default_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def load_schema_on_branch(
        self,
        client: InfrahubClient,
        setup_branch: Branch,
        schema_with_numberpool: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_with_numberpool], branch=setup_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def schemas_loaded(
        self,
        load_schema_on_default: None,
        load_schema_on_branch: None,
    ) -> None:
        """Fixture that ensures schemas are loaded on both branches before proceeding."""

    @pytest.fixture(scope="class")
    async def create_server_on_default(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schemas_loaded: None,
    ) -> Node:
        server = await Node.init(schema=SERVER_KIND, db=db, branch=default_branch)
        await server.new(db=db, name="server-default")
        await server.save(db=db)
        return server

    @pytest.fixture(scope="class")
    async def create_server_on_branch(
        self,
        db: InfrahubDatabase,
        setup_branch: Branch,
        schemas_loaded: None,
    ) -> Node:
        server = await Node.init(schema=SERVER_KIND, db=db, branch=setup_branch)
        await server.new(db=db, name="server-branch")
        await server.save(db=db)
        return server

    async def test_instance_creation_fails_without_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        setup_branch: Branch,
        schemas_loaded: None,
    ) -> None:
        """Validate that creating instances fails when the NumberPool doesn't exist yet."""
        branches = [
            (default_branch, "default"),
            (setup_branch, "branch"),
        ]

        for branch, branch_label in branches:
            # Get the number_pool_id from the branch schema
            schema = registry.schema.get_node_schema(name=SERVER_KIND, branch=branch.name)
            rack_unit_attr = schema.get_attribute(name="rack_unit")
            assert isinstance(rack_unit_attr.parameters, NumberPoolParameters)
            number_pool_id = rack_unit_attr.parameters.number_pool_id
            assert number_pool_id is not None, f"{branch_label} branch schema should have a number_pool_id assigned"

            # Try to create on this branch - should fail
            with pytest.raises(ValidationError) as exc_info:
                server = await Node.init(schema=SERVER_KIND, db=db, branch=branch)
                await server.new(db=db, name=f"server-should-fail-{branch_label}")
                await server.save(db=db)

            error_message = str(exc_info.value)
            assert "rack_unit.from_pool" in error_message, f"Expected 'rack_unit.from_pool' in error: {error_message}"
            assert "was not found" in error_message, f"Expected 'was not found' in error: {error_message}"
            assert number_pool_id in error_message, f"Expected pool ID {number_pool_id} in error: {error_message}"

    async def test_validator_creates_single_pool(
        self,
        db: InfrahubDatabase,
        schemas_loaded: None,
    ) -> None:
        """Validate that SchemaNumberPoolValidator creates exactly one CoreNumberPool after schemas are loaded."""
        # Run the validator
        validator = SchemaNumberPoolValidator(
            db=db,
            log=log,
            schema_manager=registry.schema,
        )
        await validator.run()

        # Query for all schema-type number pools
        pools = await NodeManager.query(
            db=db,
            schema="CoreNumberPool",
            filters={"pool_type__value": NumberPoolType.SCHEMA.value},
            branch_agnostic=True,
        )

        # Filter to find pools for the TestingServer.rack_unit attribute
        server_pools = [
            pool
            for pool in pools
            if pool.get_attribute("node").value == SERVER_KIND
            and pool.get_attribute("node_attribute").value == "rack_unit"
        ]

        assert len(server_pools) == 1, (
            f"Expected exactly 1 CoreNumberPool for {SERVER_KIND}.rack_unit after running validator, "
            f"found {len(server_pools)}"
        )

        # Verify the pool has the correct range
        pool = server_pools[0]
        assert pool.get_attribute("start_range").value == 1
        assert pool.get_attribute("end_range").value == 42

    async def test_single_numberpool_instance_exists(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        setup_branch: Branch,
        schemas_loaded: None,
        create_server_on_default: Node,
        create_server_on_branch: Node,
    ) -> None:
        """Validate that only one CoreNumberPool instance exists after creating objects on multiple branches."""
        pools = await NodeManager.query(db=db, schema="CoreNumberPool", branch_agnostic=True)

        # Filter to find pools for the TestingServer.rack_unit attribute
        server_pools = [
            pool
            for pool in pools
            if pool.get_attribute("node").value == SERVER_KIND
            and pool.get_attribute("node_attribute").value == "rack_unit"
        ]

        assert len(server_pools) == 1, (
            f"Expected exactly 1 CoreNumberPool for {SERVER_KIND}.rack_unit, found {len(server_pools)}"
        )

    async def test_instances_have_unique_values(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        setup_branch: Branch,
        create_server_on_default: Node,
        create_server_on_branch: Node,
    ) -> None:
        """Validate that instances created on different branches got unique attribute values."""
        # Re-query to get fresh values
        default_servers = await registry.manager.query(db=db, schema=SERVER_KIND, branch=default_branch)
        branch_servers = await registry.manager.query(db=db, schema=SERVER_KIND, branch=setup_branch)

        assert len(default_servers) == 1
        assert len(branch_servers) == 1

        default_value = default_servers[0].rack_unit.value
        branch_value = branch_servers[0].rack_unit.value

        # Both should have received values
        assert default_value is not None, "Server on default branch should have a rack_unit value"
        assert branch_value is not None, "Server on user branch should have a rack_unit value"

        # Values should be unique (different)
        assert default_value != branch_value, (
            f"Servers on different branches should have unique rack_unit values, but both got {default_value}"
        )

        # Values should be within the pool range (1-42)
        assert 1 <= default_value <= 42, f"rack_unit value {default_value} is outside pool range 1-42"
        assert 1 <= branch_value <= 42, f"rack_unit value {branch_value} is outside pool range 1-42"

    async def test_schema_number_pool_id_matches_pool_in_registry(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        setup_branch: Branch,
        create_server_on_default: Node,
        create_server_on_branch: Node,
    ) -> None:
        """Validate that the schema's number_pool_id in the registry matches the actual CoreNumberPool ID."""
        # Get the actual pool
        pools = await NodeManager.query(db=db, schema="CoreNumberPool", branch_agnostic=True)
        server_pools = [
            pool
            for pool in pools
            if pool.get_attribute("node").value == SERVER_KIND
            and pool.get_attribute("node_attribute").value == "rack_unit"
        ]
        assert len(server_pools) == 1
        actual_pool_id = server_pools[0].id

        # Check the schema on default branch in registry
        default_schema = registry.schema.get_node_schema(name=SERVER_KIND, branch=default_branch.name)
        default_attr = default_schema.get_attribute(name="rack_unit")
        assert isinstance(default_attr.parameters, NumberPoolParameters)
        assert default_attr.parameters.number_pool_id == actual_pool_id, (
            f"Default branch registry schema number_pool_id ({default_attr.parameters.number_pool_id}) "
            f"doesn't match actual pool ID ({actual_pool_id})"
        )

        # Check the schema on user branch in registry
        branch_schema = registry.schema.get_node_schema(name=SERVER_KIND, branch=setup_branch.name)
        branch_attr = branch_schema.get_attribute(name="rack_unit")
        assert isinstance(branch_attr.parameters, NumberPoolParameters)
        assert branch_attr.parameters.number_pool_id == actual_pool_id, (
            f"User branch registry schema number_pool_id ({branch_attr.parameters.number_pool_id}) "
            f"doesn't match actual pool ID ({actual_pool_id})"
        )

    async def test_schema_number_pool_id_matches_pool_in_database(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        setup_branch: Branch,
        create_server_on_default: Node,
        create_server_on_branch: Node,
    ) -> None:
        """Validate that the schema's number_pool_id in the database matches the actual CoreNumberPool ID."""
        # Get the actual pool
        pools = await NodeManager.query(db=db, schema="CoreNumberPool", branch_agnostic=True)
        server_pools = [
            pool
            for pool in pools
            if pool.get_attribute("node").value == SERVER_KIND
            and pool.get_attribute("node_attribute").value == "rack_unit"
        ]
        assert len(server_pools) == 1
        actual_pool_id = server_pools[0].id

        # Load schema fresh from database for default branch
        default_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        default_schema_from_db = default_schema_branch.get_node(name=SERVER_KIND)
        default_attr_from_db = default_schema_from_db.get_attribute(name="rack_unit")
        assert isinstance(default_attr_from_db.parameters, NumberPoolParameters)
        assert default_attr_from_db.parameters.number_pool_id == actual_pool_id, (
            f"Default branch database schema number_pool_id ({default_attr_from_db.parameters.number_pool_id}) "
            f"doesn't match actual pool ID ({actual_pool_id})"
        )

        # Load schema fresh from database for user branch
        branch_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=setup_branch)
        branch_schema_from_db = branch_schema_branch.get_node(name=SERVER_KIND)
        branch_attr_from_db = branch_schema_from_db.get_attribute(name="rack_unit")
        assert isinstance(branch_attr_from_db.parameters, NumberPoolParameters)
        assert branch_attr_from_db.parameters.number_pool_id == actual_pool_id, (
            f"User branch database schema number_pool_id ({branch_attr_from_db.parameters.number_pool_id}) "
            f"doesn't match actual pool ID ({actual_pool_id})"
        )
