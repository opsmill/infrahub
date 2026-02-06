from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import NumberPoolType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
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
        setup_branch: Branch,
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
            assert number_pool_id is None, f"{branch_label} branch schema should not have a number_pool_id assigned"

            # Try to create on this branch - should fail
            with pytest.raises(ValidationError) as exc_info:
                server = await Node.init(schema=SERVER_KIND, db=db, branch=branch)
                await server.new(db=db, name=f"server-should-fail-{branch_label}")
                await server.save(db=db)

            error_message = str(exc_info.value)
            assert "The pool for rack_unit has not been provisioned yet" in error_message

    async def test_validator_creates_single_pool(
        self,
        db: InfrahubDatabase,
        schemas_loaded: None,
    ) -> None:
        """Validate that SchemaNumberPoolSynchronizer creates exactly one CoreNumberPool after schemas are loaded."""
        # Run the validator
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        synchronizer = SchemaNumberPoolSynchronizer(
            db=db,
            log=log,
            schema_manager=registry.schema,
            upserter=upserter,
        )
        await synchronizer.run()

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


class TestInheritedNumberPoolReusesExistingPool(TestInfrahubApp):
    """Test that a new node inheriting from an existing generic with a NumberPool reuses the existing pool.

    This test verifies:
    1. Load a generic with a NumberPool attribute
    2. Run synchronizer to create the CoreNumberPool
    3. Load a new node that inherits from the generic
    4. Verify the node's inherited attribute uses the SAME pool (no new pool created)
    """

    @pytest.fixture(scope="class")
    def generic_schema_with_numberpool(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [
                {
                    "name": "BaseTask",
                    "namespace": "Testing",
                    "include_in_menu": False,
                    "label": "Base Task",
                    "attributes": [
                        {"name": "title", "kind": "Text"},
                        {
                            "name": "ticket_number",
                            "kind": "NumberPool",
                            "optional": False,
                            "read_only": True,
                            "unique": True,
                            "parameters": {"start_range": 1000, "end_range": 9999},
                        },
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    def node_inheriting_from_generic(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Incident",
                    "namespace": "Testing",
                    "inherit_from": ["TestingBaseTask"],
                    "include_in_menu": True,
                    "label": "Incident",
                    "attributes": [
                        {"name": "severity", "kind": "Text"},
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    async def load_generic_schema(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        generic_schema_with_numberpool: dict[str, Any],
    ) -> None:
        """Load the generic schema first."""
        response = await client.schema.load(schemas=[generic_schema_with_numberpool], branch=default_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def run_synchronizer_for_generic(
        self,
        db: InfrahubDatabase,
        load_generic_schema: None,
    ) -> str:
        """Run the synchronizer to create the CoreNumberPool for the generic."""
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        synchronizer = SchemaNumberPoolSynchronizer(
            db=db,
            log=log,
            schema_manager=registry.schema,
            upserter=upserter,
        )
        await synchronizer.run()

        # Get the pool ID that was created
        pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={
                "node__value": "TestingBaseTask",
                "node_attribute__value": "ticket_number",
                "pool_type__value": NumberPoolType.SCHEMA.value,
            },
            branch_agnostic=True,
        )
        assert len(pools) == 1, "Expected exactly one pool for TestingBaseTask.ticket_number"
        return pools[0].id

    @pytest.fixture(scope="class")
    async def load_inheriting_node_schema(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        node_inheriting_from_generic: dict[str, Any],
        run_synchronizer_for_generic: str,
    ) -> None:
        """Load the node schema that inherits from the generic."""
        response = await client.schema.load(schemas=[node_inheriting_from_generic], branch=default_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def run_synchronizer_after_node_added(
        self,
        db: InfrahubDatabase,
        load_inheriting_node_schema: None,
    ) -> None:
        """Run the synchronizer again after adding the inheriting node."""
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        synchronizer = SchemaNumberPoolSynchronizer(
            db=db,
            log=log,
            schema_manager=registry.schema,
            upserter=upserter,
        )
        await synchronizer.run()

    async def test_no_new_pool_created_for_inherited_attribute(
        self,
        db: InfrahubDatabase,
        run_synchronizer_for_generic: str,
        run_synchronizer_after_node_added: None,
    ) -> None:
        """Verify that no new pool was created when the inheriting node was added."""
        original_pool_id = run_synchronizer_for_generic

        # Query for all pools related to ticket_number attribute
        all_pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={
                "pool_type__value": NumberPoolType.SCHEMA.value,
            },
            branch_agnostic=True,
        )

        # Should still be exactly one pool
        assert len(all_pools) == 1, (
            f"Expected exactly 1 pool for ticket_number attribute, found {len(all_pools)}. "
            "A new pool should NOT be created for the inherited attribute."
        )
        the_pool = all_pools[0]
        assert the_pool.node.value == "TestingBaseTask", "Pool should reference the generic 'TestingBaseTask'"
        assert the_pool.node_attribute.value == "ticket_number", "Pool should reference attribute 'ticket_number'"

        # And it should be the same pool as before
        assert the_pool.id == original_pool_id, (
            f"Pool ID changed from {original_pool_id} to {the_pool.id}. "
            "The inherited attribute should use the existing pool."
        )

    async def test_inherited_attribute_uses_generic_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        run_synchronizer_for_generic: str,
        run_synchronizer_after_node_added: None,
    ) -> None:
        """Verify that the inherited attribute on the node has the same pool ID as the generic."""
        original_pool_id = run_synchronizer_for_generic

        # Get the generic's attribute pool ID from registry
        generic_schema = registry.schema.get_generic_schema(name="TestingBaseTask", branch=default_branch.name)
        generic_attr = generic_schema.get_attribute(name="ticket_number")
        assert isinstance(generic_attr.parameters, NumberPoolParameters)
        assert generic_attr.parameters.number_pool_id == original_pool_id

        # Get the node's inherited attribute pool ID from registry
        node_schema = registry.schema.get_node_schema(name="TestingIncident", branch=default_branch.name)
        node_attr = node_schema.get_attribute(name="ticket_number")
        assert isinstance(node_attr.parameters, NumberPoolParameters)

        # The inherited attribute should have the SAME pool ID as the generic
        assert node_attr.parameters.number_pool_id == original_pool_id, (
            f"Inherited attribute pool ID ({node_attr.parameters.number_pool_id}) "
            f"doesn't match generic's pool ID ({original_pool_id})"
        )

    async def test_pool_references_generic_not_node(
        self,
        db: InfrahubDatabase,
        run_synchronizer_for_generic: str,
        run_synchronizer_after_node_added: None,
    ) -> None:
        """Verify that only one CoreNumberPool exists and it references the generic (not the inheriting node)."""
        original_pool_id = run_synchronizer_for_generic

        # Query ALL schema-type number pools
        all_schema_pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={"pool_type__value": NumberPoolType.SCHEMA.value},
            branch_agnostic=True,
        )

        # Should be exactly one pool total
        assert len(all_schema_pools) == 1, (
            f"Expected exactly 1 schema-type CoreNumberPool, found {len(all_schema_pools)}. "
            f"Pool IDs: {[p.id for p in all_schema_pools]}"
        )

        pool = all_schema_pools[0]

        # Verify it's the original pool
        assert pool.id == original_pool_id, f"Pool ID ({pool.id}) doesn't match original ({original_pool_id})"

        # The pool should reference the generic (where the attribute is defined)
        assert pool.node.value == "TestingBaseTask", (
            f"Pool should reference the generic 'TestingBaseTask', not '{pool.node.value}'"
        )
        assert pool.node_attribute.value == "ticket_number", (
            f"Pool should reference attribute 'ticket_number', not '{pool.node_attribute.value}'"
        )

    async def test_create_instances_share_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        run_synchronizer_after_node_added: None,
    ) -> None:
        """Verify that instances of the inheriting node get values from the shared pool."""
        # Create an instance of the inheriting node
        incident = await Node.init(schema="TestingIncident", db=db, branch=default_branch)
        await incident.new(db=db, title="Test Incident", severity="High")
        await incident.save(db=db)

        # The ticket_number should have been allocated from the pool
        assert incident.ticket_number.value is not None
        assert 1000 <= incident.ticket_number.value <= 9999, (
            f"ticket_number value {incident.ticket_number.value} is outside pool range 1000-9999"
        )


class TestAddNumberPoolToExistingGenericWithInheritingNode(TestInfrahubApp):
    """Test that adding a NumberPool attribute to an existing generic with inheriting nodes works correctly.

    This test verifies:
    1. A generic and inheriting node exist WITHOUT a NumberPool attribute
    2. Add a NumberPool attribute to the generic (schema migrations create the CoreNumberPool)
    3. Verify the generic and inheriting node both have the SAME number_pool_id
    4. Verify no separate CoreNumberPool is created for the inheriting node
    """

    @pytest.fixture(scope="class")
    def generic_without_numberpool(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [
                {
                    "name": "BaseEquipment",
                    "namespace": "Testing",
                    "include_in_menu": False,
                    "label": "Base Equipment",
                    "attributes": [
                        {"name": "description", "kind": "Text"},
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "NetworkDevice",
                    "namespace": "Testing",
                    "inherit_from": ["TestingBaseEquipment"],
                    "include_in_menu": True,
                    "label": "Network Device",
                    "attributes": [
                        {"name": "hostname", "kind": "Text", "unique": True},
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    def generic_with_numberpool(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [
                {
                    "name": "BaseEquipment",
                    "namespace": "Testing",
                    "include_in_menu": False,
                    "label": "Base Equipment",
                    "attributes": [
                        {"name": "description", "kind": "Text"},
                        {
                            "name": "asset_tag",
                            "kind": "NumberPool",
                            "optional": False,
                            "read_only": True,
                            "unique": True,
                            "parameters": {"start_range": 100000, "end_range": 999999},
                        },
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    async def load_initial_schema(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        generic_without_numberpool: dict[str, Any],
    ) -> None:
        """Load the generic and inheriting node WITHOUT the NumberPool attribute."""
        await client.schema.load(schemas=[generic_without_numberpool], branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def add_numberpool_to_generic(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        generic_with_numberpool: dict[str, Any],
        load_initial_schema: None,
    ) -> None:
        """Add the NumberPool attribute to the existing generic (migrations create the pool)."""
        await client.schema.load(schemas=[generic_with_numberpool], branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def run_synchronizer(
        self,
        db: InfrahubDatabase,
        add_numberpool_to_generic: None,
    ) -> None:
        """Run SchemaNumberPoolSynchronizer to update schema with pool IDs.

        In integration tests, the synchronizer doesn't run automatically (it relies on events).
        We run it manually to update the number_pool_id in the schema's attribute parameters.
        """
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        synchronizer = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
        await synchronizer.run()

    async def test_only_one_pool_exists(
        self,
        db: InfrahubDatabase,
        add_numberpool_to_generic: None,
    ) -> None:
        """Verify that only one CoreNumberPool was created (not one for each schema)."""
        # Query for all pools related to asset_tag attribute
        all_pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={
                "node_attribute__value": "asset_tag",
                "pool_type__value": NumberPoolType.SCHEMA.value,
            },
            branch_agnostic=True,
        )

        # Should be exactly one pool
        assert len(all_pools) == 1, (
            f"Expected exactly 1 pool for asset_tag attribute, found {len(all_pools)}. "
            "A separate pool should NOT be created for the inheriting node."
        )

        # And it should reference the generic
        the_pool = all_pools[0]
        assert the_pool.node.value == "TestingBaseEquipment", (
            f"Pool should reference the generic 'TestingBaseEquipment', not '{the_pool.node.value}'"
        )

    async def test_generic_and_node_have_same_pool_id(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        run_synchronizer: None,
    ) -> None:
        """Verify that both the generic and inheriting node have the same number_pool_id after synchronizer runs."""
        # Get the generic's attribute pool ID from registry
        generic_schema = registry.schema.get_generic_schema(name="TestingBaseEquipment", branch=default_branch.name)
        generic_attr = generic_schema.get_attribute(name="asset_tag")
        assert isinstance(generic_attr.parameters, NumberPoolParameters)
        generic_pool_id = generic_attr.parameters.number_pool_id
        assert generic_pool_id is not None, "Generic attribute should have a number_pool_id assigned"

        # Get the node's inherited attribute pool ID from registry
        node_schema = registry.schema.get_node_schema(name="TestingNetworkDevice", branch=default_branch.name)
        node_attr = node_schema.get_attribute(name="asset_tag")
        assert isinstance(node_attr.parameters, NumberPoolParameters)
        assert node_attr.parameters.number_pool_id == generic_pool_id, (
            f"Inherited attribute pool ID ({node_attr.parameters.number_pool_id}) "
            f"doesn't match generic's pool ID ({generic_pool_id})"
        )

    async def test_no_pool_for_node(
        self,
        db: InfrahubDatabase,
        add_numberpool_to_generic: None,
    ) -> None:
        """Verify that no CoreNumberPool was created for the inheriting node."""
        # Query for pools that reference the inheriting node
        node_pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={
                "node__value": "TestingNetworkDevice",
                "pool_type__value": NumberPoolType.SCHEMA.value,
            },
            branch_agnostic=True,
        )

        assert len(node_pools) == 0, (
            f"No pool should exist for 'TestingNetworkDevice', but found {len(node_pools)}. "
            "Inherited attributes should use the generic's pool."
        )

    async def test_create_instance_uses_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        run_synchronizer: None,
    ) -> None:
        """Verify that creating an instance of the inheriting node allocates from the shared pool."""
        # Create an instance of the inheriting node
        device = await Node.init(schema="TestingNetworkDevice", db=db, branch=default_branch)
        await device.new(db=db, hostname="router-01", description="Core router")
        await device.save(db=db)

        # The asset_tag should have been allocated from the pool
        assert device.asset_tag.value is not None
        assert 100000 <= device.asset_tag.value <= 999999, (
            f"asset_tag value {device.asset_tag.value} is outside pool range 100000-999999"
        )
