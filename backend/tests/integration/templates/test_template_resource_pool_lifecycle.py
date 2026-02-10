"""Integration tests for _from_resource_pool relationships on TemplateSchemas.

Tests that _from_resource_pool relationships are correctly added and removed from
TemplateSchemas when the associated Node or GenericSchema is updated in a manner
that would add or remove support for a _from_resource_pool relationship.

Covers:
- Adding/removing BuiltinIPAddress/BuiltinIPPrefix peer relationships on Node and Generic
- Changing a relationship peer to/from IP types
- Setting pool instances on template instances and verifying retrieval via the SDK
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestTemplateResourcePoolLifecycle(TestInfrahubApp):
    """Test _from_resource_pool relationships lifecycle on templates.

    Uses a Generic (TestingEndpoint) with a non-IP relationship and a Node (TestingDevice)
    that inherits from it. Schema updates add/remove/change BuiltinIPAddress and BuiltinIPPrefix
    peer relationships, and the tests verify the corresponding _from_resource_pool relationships
    on the TemplateTestingDevice schema and instances.
    """

    # --- Schema component fixtures ---

    @pytest.fixture(scope="class")
    def ip_address_schema(self) -> NodeSchema:
        return NodeSchema(
            name="IPAddress",
            namespace="Ipam",
            inherit_from=["BuiltinIPAddress"],
        )

    @pytest.fixture(scope="class")
    def ip_prefix_schema(self) -> NodeSchema:
        return NodeSchema(
            name="IPPrefix",
            namespace="Ipam",
            inherit_from=["BuiltinIPPrefix"],
        )

    @pytest.fixture(scope="class")
    def vlan_schema_base(self) -> NodeSchema:
        return NodeSchema(
            name="Vlan",
            namespace="Testing",
            label="VLAN",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="vlan_id", kind="Number"),
            ],
        )

    @pytest.fixture(scope="class")
    def generic_schema_base(self) -> GenericSchema:
        """Generic with a non-IP relationship initially."""
        return GenericSchema(
            name="Endpoint",
            namespace="Testing",
            generate_template=True,
            attributes=[
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="connected_vlan",
                    peer="TestingVlan",
                    label="Connected VLAN",
                    cardinality=RelationshipCardinality.ONE,
                    optional=True,
                ),
            ],
        )

    @pytest.fixture(scope="class")
    def device_schema_base(self) -> NodeSchema:
        """Node inheriting from Generic, with generate_template=True."""
        return NodeSchema(
            name="Device",
            namespace="Testing",
            generate_template=True,
            inherit_from=["TestingEndpoint"],
            label="Device",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="role", kind="Text", optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    def mgmt_address_rel(self) -> RelationshipSchema:
        """BuiltinIPAddress relationship for mgmt_address on Device."""
        return RelationshipSchema(
            name="mgmt_address",
            peer="BuiltinIPAddress",
            label="Management Address",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        )

    @pytest.fixture(scope="class")
    def network_prefix_rel(self) -> RelationshipSchema:
        """BuiltinIPPrefix relationship for network_prefix on Endpoint."""
        return RelationshipSchema(
            name="network_prefix",
            peer="BuiltinIPPrefix",
            label="Network Prefix",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        )

    async def _load_schema_and_assert(
        self,
        client: InfrahubClient,
        branch_name: str,
        generics: list[GenericSchema] | None = None,
        nodes: list[NodeSchema] | None = None,
    ) -> None:
        """Load schema via client and assert it was updated without errors."""
        schema_root = SchemaRoot(
            version="1.0",
            generics=generics or [],
            nodes=nodes or [],
        )
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=branch_name)
        assert response.schema_updated
        assert not response.errors

    # -------------------------------------------------------------------------
    # Phase 1: Initial schema with no IP relationships
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_01(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ip_address_schema: NodeSchema,
        ip_prefix_schema: NodeSchema,
        vlan_schema_base: NodeSchema,
        generic_schema_base: GenericSchema,
        device_schema_base: NodeSchema,
    ) -> None:
        """Load initial schema: Device inherits from Endpoint, no IP relationships."""
        schema_root = SchemaRoot(
            version="1.0",
            generics=[generic_schema_base],
            nodes=[ip_address_schema, ip_prefix_schema, vlan_schema_base, device_schema_base],
        )
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    # --- Pool prerequisite fixtures ---

    @pytest.fixture(scope="class")
    async def ip_namespace(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_01: None,
    ) -> Node:
        """Create an IP namespace for pool resources."""
        ns = await Node.init(db=db, schema=InfrahubKind.IPNAMESPACE)
        await ns.new(db=db, name="pool-test-ns")
        await ns.save(db=db)
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix_resource(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ip_namespace: Node,
    ) -> Node:
        """Create an IP prefix to serve as a pool resource."""
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        prefix = await Node.init(db=db, schema=prefix_schema)
        await prefix.new(db=db, prefix="10.0.0.0/8", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def address_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ip_prefix_resource: Node,
        ip_namespace: Node,
    ) -> Node:
        """Create a CoreIPAddressPool instance."""
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
        pool = await Node.init(db=db, schema=pool_schema)
        await pool.new(
            db=db,
            name="test-address-pool",
            default_address_type="IpamIPAddress",
            resources=[ip_prefix_resource],
            ip_namespace=ip_namespace,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def prefix_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ip_prefix_resource: Node,
        ip_namespace: Node,
    ) -> Node:
        """Create a CoreIPPrefixPool instance."""
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
        pool = await Node.init(db=db, schema=pool_schema)
        await pool.new(
            db=db,
            name="test-prefix-pool",
            resources=[ip_prefix_resource],
            ip_namespace=ip_namespace,
        )
        await pool.save(db=db)
        return pool

    # --- Template instance ---

    @pytest.fixture(scope="class")
    async def node_template_instance(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_01: None,
    ) -> Node:
        """Create a template instance before adding IP relationships."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
        template = await Node.init(db=db, schema=template_schema)
        await template.new(
            db=db,
            template_name="device_template_01",
            role="router",
        )
        await template.save(db=db)
        return template

    @pytest.fixture(scope="class")
    async def generic_template_instance(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        schema_step_01: None,
    ) -> Node:
        """Create an endpoint template instance before adding IP relationships."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingEndpoint", branch=default_branch, duplicate=False
        )
        template = await Node.init(db=db, schema=template_schema)
        await template.new(
            db=db,
            template_name="endpoint_template_01",
            description="test endpoint",
        )
        await template.save(db=db)
        return template

    async def test_step_01_initial_template_has_no_resource_pool_rels(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_01: None,
        node_template_instance: Node,
        generic_template_instance: Node,
    ) -> None:
        """Verify initial template has no _from_resource_pool relationships."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan" in rel_names
        pool_rels = {name for name in rel_names if "from_resource_pool" in name}
        assert pool_rels == set()

    async def test_step_01b_initial_endpoint_template_has_no_resource_pool_rels(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_01: None,
    ) -> None:
        """Verify initial endpoint template has no _from_resource_pool relationships."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan" in rel_names
        pool_rels = {name for name in rel_names if "from_resource_pool" in name}
        assert pool_rels == set()

    # -------------------------------------------------------------------------
    # Phase 2: Add BuiltinIPAddress relationship to Node
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_02(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        node_template_instance: Node,
        generic_template_instance: Node,
        device_schema_base: NodeSchema,
        mgmt_address_rel: RelationshipSchema,
    ) -> None:
        """Add a BuiltinIPAddress relationship to the Device node schema."""
        updated_device = device_schema_base.model_copy(deep=True)
        updated_device.relationships.append(mgmt_address_rel.model_copy(deep=True))
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            generics=[],
            nodes=[updated_device],
        )

    async def test_step_02_add_builtin_ip_address_rel_creates_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_02: None,
    ) -> None:
        """Adding a BuiltinIPAddress relationship should create mgmt_address_from_resource_pool."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "mgmt_address" in rel_names
        assert "mgmt_address_from_resource_pool" in rel_names

        pool_rels = {rel.name: rel for rel in template_schema.relationships}
        assert pool_rels["mgmt_address_from_resource_pool"].peer == InfrahubKind.IPADDRESSPOOL
        assert pool_rels["mgmt_address_from_resource_pool"].cardinality == "one"
        assert pool_rels["mgmt_address_from_resource_pool"].optional is True

        # connected_vlan is not IP, should have no pool rel
        assert "connected_vlan_from_resource_pool" not in rel_names

    async def test_step_02b_set_address_pool_on_template_instance(
        self,
        client: InfrahubClient,
        node_template_instance: Node,
        address_pool: Node,
        schema_step_02: None,
    ) -> None:
        """Set address pool on template instance and verify retrieval."""
        # Update the template instance to set the address pool
        template = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        template.mgmt_address_from_resource_pool = address_pool.id
        await template.save()

        # Retrieve and verify the pool is set
        retrieved = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        assert retrieved.role.value == "router"
        assert retrieved.mgmt_address_from_resource_pool.id == address_pool.id

    async def test_step_02c_endpoint_template_unaffected_by_node_rel_add(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_02: None,
    ) -> None:
        """Adding IP rel to Node should not affect the Generic's template."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "mgmt_address" not in rel_names
        assert "mgmt_address_from_resource_pool" not in rel_names
        pool_rels = {name for name in rel_names if "from_resource_pool" in name}
        assert pool_rels == set()

    # -------------------------------------------------------------------------
    # Phase 3: Add BuiltinIPPrefix relationship to Generic
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_03(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        schema_step_02: None,
        generic_schema_base: GenericSchema,
        network_prefix_rel: RelationshipSchema,
    ) -> None:
        """Add a BuiltinIPPrefix relationship to the Generic (TestingEndpoint)."""
        updated_generic = generic_schema_base.model_copy(deep=True)
        updated_generic.relationships.append(network_prefix_rel.model_copy(deep=True))
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            generics=[updated_generic],
        )

    async def test_step_03_add_builtin_ip_prefix_rel_to_generic_creates_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_03: None,
    ) -> None:
        """Adding BuiltinIPPrefix relationship to Generic should create network_prefix_from_resource_pool."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "network_prefix" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

        pool_rels = {rel.name: rel for rel in template_schema.relationships}
        assert pool_rels["network_prefix_from_resource_pool"].peer == InfrahubKind.IPPREFIXPOOL
        assert pool_rels["network_prefix_from_resource_pool"].optional is True

        # mgmt_address pool rel should still be there
        assert "mgmt_address_from_resource_pool" in rel_names

    async def test_step_03b_set_prefix_pool_on_template_instance(
        self,
        client: InfrahubClient,
        node_template_instance: Node,
        prefix_pool: Node,
        address_pool: Node,
        schema_step_03: None,
    ) -> None:
        """Set prefix pool on template instance and verify both pools are present."""
        # Update the template instance to set the prefix pool
        template = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        template.network_prefix_from_resource_pool = prefix_pool.id
        await template.save()

        # Retrieve and verify both pools are set
        retrieved = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        assert retrieved.network_prefix_from_resource_pool.id == prefix_pool.id
        assert retrieved.mgmt_address_from_resource_pool.id == address_pool.id

    async def test_step_03c_endpoint_template_gets_prefix_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_03: None,
    ) -> None:
        """Adding BuiltinIPPrefix to Generic should create pool rel on endpoint template too."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "network_prefix" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

        pool_rels = {rel.name: rel for rel in template_schema.relationships}
        assert pool_rels["network_prefix_from_resource_pool"].peer == InfrahubKind.IPPREFIXPOOL

    async def test_step_03d_set_prefix_pool_on_generic_template_instance(
        self,
        client: InfrahubClient,
        generic_template_instance: Node,
        prefix_pool: Node,
        schema_step_03: None,
    ) -> None:
        """Set prefix pool on endpoint template instance and verify retrieval."""
        template = await client.get(
            kind="TemplateTestingEndpoint",
            template_name__value="endpoint_template_01",
        )
        template.network_prefix_from_resource_pool = prefix_pool.id
        await template.save()

        retrieved = await client.get(
            kind="TemplateTestingEndpoint",
            template_name__value="endpoint_template_01",
        )
        assert retrieved.description.value == "test endpoint"
        assert retrieved.network_prefix_from_resource_pool.id == prefix_pool.id

    # -------------------------------------------------------------------------
    # Phase 4: Change Generic's connected_vlan peer to BuiltinIPAddress
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_04(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        schema_step_03: None,
        generic_schema_base: GenericSchema,
        network_prefix_rel: RelationshipSchema,
    ) -> None:
        """Change connected_vlan peer from TestingVlan to BuiltinIPAddress."""
        updated_generic = generic_schema_base.model_copy(deep=True)
        for rel in updated_generic.relationships:
            if rel.name == "connected_vlan":
                rel.peer = "BuiltinIPAddress"
                rel.label = "Connected IP (was VLAN)"
                break
        updated_generic.relationships.append(network_prefix_rel.model_copy(deep=True))
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            generics=[updated_generic],
        )

    async def test_step_04_change_generic_rel_peer_to_ip_adds_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_04: None,
    ) -> None:
        """Changing connected_vlan peer to BuiltinIPAddress should add connected_vlan_from_resource_pool."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan" in rel_names
        assert "connected_vlan_from_resource_pool" in rel_names

        pool_rels = {rel.name: rel for rel in template_schema.relationships}
        assert pool_rels["connected_vlan_from_resource_pool"].peer == InfrahubKind.IPADDRESSPOOL

        # Other pool rels still present
        assert "mgmt_address_from_resource_pool" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

    async def test_step_04b_endpoint_template_gets_connected_vlan_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_04: None,
    ) -> None:
        """Changing connected_vlan peer to IP on Generic should add pool rel on endpoint template."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan_from_resource_pool" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

        pool_rels = {rel.name: rel for rel in template_schema.relationships}
        assert pool_rels["connected_vlan_from_resource_pool"].peer == InfrahubKind.IPADDRESSPOOL

    # -------------------------------------------------------------------------
    # Phase 5: Change connected_vlan peer back to non-IP
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_05(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        schema_step_04: None,
        generic_schema_base: GenericSchema,
        network_prefix_rel: RelationshipSchema,
    ) -> None:
        """Change connected_vlan peer back to TestingVlan (non-IP)."""
        # generic_schema_base has connected_vlan=TestingVlan already
        updated_generic = generic_schema_base.model_copy(deep=True)
        updated_generic.relationships.append(network_prefix_rel.model_copy(deep=True))
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            generics=[updated_generic],
        )

    async def test_step_05_change_peer_back_to_non_ip_removes_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_05: None,
    ) -> None:
        """Changing connected_vlan peer back to non-IP should remove connected_vlan_from_resource_pool."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan" in rel_names
        assert "connected_vlan_from_resource_pool" not in rel_names

        # Other pool rels still present
        assert "mgmt_address_from_resource_pool" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

    async def test_step_05b_endpoint_template_loses_connected_vlan_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_05: None,
    ) -> None:
        """Reverting connected_vlan peer on Generic should remove pool rel from endpoint template."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "connected_vlan_from_resource_pool" not in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

    # -------------------------------------------------------------------------
    # Phase 6: Remove mgmt_address (BuiltinIPAddress) from Node
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_06(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        schema_step_05: None,
        device_schema_base: NodeSchema,
        mgmt_address_rel: RelationshipSchema,
    ) -> None:
        """Remove the mgmt_address relationship from the Device node."""
        current_device_schema = await client.schema.get(kind="TestingDevice", branch=default_branch.name, refresh=True)
        mgmt_address_id = None
        for rel in current_device_schema.relationships:
            if rel.name == "mgmt_address":
                mgmt_address_id = rel.id
                break
        assert mgmt_address_id is not None

        updated_device = device_schema_base.model_copy(deep=True)
        absent_rel = mgmt_address_rel.model_copy(
            deep=True, update={"id": mgmt_address_id, "state": HashableModelState.ABSENT}
        )
        updated_device.relationships.append(absent_rel)
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            nodes=[updated_device],
        )

    async def test_step_06_remove_node_ip_rel_removes_its_pool_rel(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_06: None,
    ) -> None:
        """Removing mgmt_address should remove mgmt_address_from_resource_pool but keep network_prefix pool rel."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        assert "mgmt_address" not in rel_names
        assert "mgmt_address_from_resource_pool" not in rel_names

        # Generic's prefix pool rel should still be there
        assert "network_prefix" in rel_names
        assert "network_prefix_from_resource_pool" in rel_names

    async def test_step_06b_remaining_prefix_pool_still_on_template(
        self,
        client: InfrahubClient,
        node_template_instance: Node,
        prefix_pool: Node,
        schema_step_06: None,
    ) -> None:
        """Verify the prefix pool is still set on the template instance after removing the address rel."""
        retrieved = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        assert retrieved.role.value == "router"
        assert retrieved.network_prefix_from_resource_pool.id == prefix_pool.id

    async def test_step_06c_endpoint_template_unaffected_by_node_rel_remove(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_06: None,
    ) -> None:
        """Removing IP rel from Node should not affect the Generic's template."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}
        assert "network_prefix_from_resource_pool" in rel_names

    async def test_step_06d_prefix_pool_still_on_endpoint_template(
        self,
        client: InfrahubClient,
        generic_template_instance: Node,
        prefix_pool: Node,
        schema_step_06: None,
    ) -> None:
        """Verify the prefix pool is still set on the endpoint template instance."""
        retrieved = await client.get(
            kind="TemplateTestingEndpoint",
            template_name__value="endpoint_template_01",
        )
        assert retrieved.description.value == "test endpoint"
        assert retrieved.network_prefix_from_resource_pool.id == prefix_pool.id

    # -------------------------------------------------------------------------
    # Phase 7: Remove network_prefix (BuiltinIPPrefix) from Generic
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def schema_step_07(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        schema_step_06: None,
        generic_schema_base: GenericSchema,
        network_prefix_rel: RelationshipSchema,
    ) -> None:
        """Remove the network_prefix relationship from the Generic."""
        current_generic_schema = await client.schema.get(
            kind="TestingEndpoint", branch=default_branch.name, refresh=True
        )
        network_prefix_id = None
        for rel in current_generic_schema.relationships:
            if rel.name == "network_prefix":
                network_prefix_id = rel.id
                break
        assert network_prefix_id is not None

        updated_generic = generic_schema_base.model_copy(deep=True)
        absent_rel = network_prefix_rel.model_copy(
            deep=True, update={"id": network_prefix_id, "state": HashableModelState.ABSENT}
        )
        updated_generic.relationships.append(absent_rel)
        await self._load_schema_and_assert(
            client=client,
            branch_name=default_branch.name,
            generics=[updated_generic],
        )

    async def test_step_07_remove_all_ip_rels_clears_all_pool_rels(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_07: None,
    ) -> None:
        """After removing all IP relationships, no _from_resource_pool relationships should remain."""
        template_schema = await client.schema.get(
            kind="TemplateTestingDevice", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        pool_rels = {name for name in rel_names if "from_resource_pool" in name}
        assert pool_rels == set()

        # connected_vlan should still be there
        assert "connected_vlan" in rel_names

    async def test_step_07b_template_instance_still_accessible(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        node_template_instance: Node,
        schema_step_07: None,
    ) -> None:
        """Verify the template instance is still accessible after all schema changes."""
        retrieved = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="device_template_01",
        )
        assert retrieved.role.value == "router"

    async def test_step_07c_endpoint_template_no_pool_rels(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_07: None,
    ) -> None:
        """After removing all IP rels, endpoint template should have no pool rels."""
        template_schema = await client.schema.get(
            kind="TemplateTestingEndpoint", branch=default_branch.name, refresh=True
        )
        rel_names = {rel.name for rel in template_schema.relationships}

        pool_rels = {name for name in rel_names if "from_resource_pool" in name}
        assert pool_rels == set()

        assert "connected_vlan" in rel_names

    async def test_step_07d_generic_template_instance_still_accessible(
        self,
        client: InfrahubClient,
        generic_template_instance: Node,
        schema_step_07: None,
    ) -> None:
        """Verify the endpoint template instance is still accessible after all schema changes."""
        retrieved = await client.get(
            kind="TemplateTestingEndpoint",
            template_name__value="endpoint_template_01",
        )
        assert retrieved.description.value == "test endpoint"
