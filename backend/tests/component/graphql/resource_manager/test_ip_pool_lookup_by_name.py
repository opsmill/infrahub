from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.initialization import create_ipam_namespace
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

FAKE_POOL_NAME = "nonexistent-pool"
PREFIX_POOL_NAME = "prefix-pool-by-name"
PREFIX_POOL_2_NAME = "prefix-pool-2-by-name"
ADDRESS_POOL_NAME = "address-pool-by-name"
ADDRESS_POOL_2_NAME = "address-pool-2-by-name"
TPL_PREFIX_POOL_NAME = "tpl-prefix-pool"
TPL_ADDRESS_POOL_NAME = "tpl-address-pool"

CREATE_PREFIX_FROM_POOL = """
mutation CreatePrefixFromPool($name: String!, $pool_id: String!) {
    TestMandatoryPrefixCreate(data: {
        name: { value: $name }
        prefix: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
        object {
            id
            prefix {
                properties {
                    source {
                        id
                    }
                }
            }
        }
    }
}
"""

CREATE_ADDRESS_FROM_POOL = """
mutation CreateAddressFromPool($name: String!, $pool_id: String!) {
    TestMandatoryAddressCreate(data: {
        name: { value: $name }
        address: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
        object {
            id
            address {
                properties {
                    source {
                        id
                    }
                }
            }
        }
    }
}
"""

UPDATE_PREFIX_FROM_POOL = """
mutation UpdatePrefixFromPool($id: String!, $pool_id: String!) {
    TestMandatoryPrefixUpdate(data: {
        id: $id
        prefix: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
    }
}
"""

UPDATE_ADDRESS_FROM_POOL = """
mutation UpdateAddressFromPool($id: String!, $pool_id: String!) {
    TestMandatoryAddressUpdate(data: {
        id: $id
        address: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
    }
}
"""


class TestIPPoolLookupByName:
    """Tests for referencing IP resource pools by name instead of UUID in from_pool."""

    @pytest.fixture(scope="class")
    async def register_ipam_schema(self, default_branch_scope_class: Branch, ipam_schema: SchemaRoot) -> SchemaBranch:
        schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    async def register_ipam_extended_schema(
        self, default_branch_scope_class: Branch, register_ipam_schema: SchemaBranch
    ) -> SchemaBranch:
        SCHEMA = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="MandatoryPrefix",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="prefix",
                            peer="IpamIPPrefix",
                            kind=RelationshipKind.ATTRIBUTE,
                            optional=False,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
                NodeSchema(
                    name="MandatoryAddress",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="address",
                            peer="IpamIPAddress",
                            kind=RelationshipKind.ATTRIBUTE,
                            optional=False,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
            ],
        )
        schema_branch = registry.schema.register_schema(schema=SCHEMA, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    def init_nodes_registry(self) -> None:
        registry.node["Node"] = Node
        registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
        registry.node[InfrahubKind.IPPREFIXPOOL] = CoreIPPrefixPool
        registry.node[InfrahubKind.IPADDRESSPOOL] = CoreIPAddressPool

    @pytest.fixture(scope="class")
    async def default_ipnamespace(
        self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch
    ) -> None:
        if not registry._default_ipnamespace:
            ip_namespace = await create_ipam_namespace(db=db)
            registry.default_ipnamespace = ip_namespace.id

    @pytest.fixture(scope="class")
    async def ip_dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_ipnamespace: None,
        register_ipam_extended_schema: SchemaBranch,
        init_nodes_registry: None,
    ) -> dict[str, Any]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch_scope_class)

        ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns1.new(db=db, name="ns1-by-name")
        await ns1.save(db=db)

        net_parent = await Node.init(db=db, schema=prefix_schema)
        await net_parent.new(db=db, prefix="10.20.0.0/16", ip_namespace=ns1)
        await net_parent.save(db=db)

        net_for_address = await Node.init(db=db, schema=prefix_schema)
        await net_for_address.new(db=db, prefix="10.20.3.0/27", parent=net_parent, ip_namespace=ns1)
        await net_for_address.save(db=db)

        net_existing = await Node.init(db=db, schema=prefix_schema)
        await net_existing.new(db=db, prefix="10.20.1.0/24", parent=net_parent, ip_namespace=ns1)
        await net_existing.save(db=db)

        return {"ns1": ns1, "net_parent": net_parent, "net_for_address": net_for_address, "net_existing": net_existing}

    @pytest.fixture(scope="class")
    async def prefix_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPPrefixPool:
        prefix_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPPREFIXPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=PREFIX_POOL_NAME,
            default_prefix_length=24,
            default_prefix_type="IpamIPPrefix",
            resources=[ip_dataset["net_parent"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def prefix_pool_2(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPPrefixPool:
        prefix_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPPREFIXPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=PREFIX_POOL_2_NAME,
            default_prefix_length=24,
            default_prefix_type="IpamIPPrefix",
            resources=[ip_dataset["net_parent"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def address_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPAddressPool:
        address_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPADDRESSPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=ADDRESS_POOL_NAME,
            default_address_type="IpamIPAddress",
            resources=[ip_dataset["net_for_address"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def address_pool_2(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPAddressPool:
        address_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPADDRESSPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=ADDRESS_POOL_2_NAME,
            default_address_type="IpamIPAddress",
            resources=[ip_dataset["net_for_address"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    # --- Prefix: create ---

    async def test_create_prefix_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, prefix_pool: CoreIPPrefixPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_PREFIX_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "site-prefix-by-name", "pool_id": PREFIX_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestMandatoryPrefixCreate"]["ok"]
        assert (
            result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["properties"]["source"]["id"] == prefix_pool.id
        )

        obj_id = result.data["TestMandatoryPrefixCreate"]["object"]["id"]
        loaded = await NodeManager.get_one(id=obj_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        prefix_rels = await loaded.get_relationship("prefix").get_relationships(db=db)
        assert len(prefix_rels) == 1
        assert prefix_rels[0].source_id == prefix_pool.id

    # --- Prefix: update (to different pool) ---

    async def test_update_prefix_from_pool_by_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        prefix_pool: CoreIPPrefixPool,
        prefix_pool_2: CoreIPPrefixPool,
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        # Create object using pool 1 by name
        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_PREFIX_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "site-update-prefix-pool", "pool_id": PREFIX_POOL_NAME},
        )
        assert not create_result.errors
        assert create_result.data
        obj_id = create_result.data["TestMandatoryPrefixCreate"]["object"]["id"]
        assert (
            create_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["properties"]["source"]["id"]
            == prefix_pool.id
        )

        # Update to use pool 2 by name
        update_result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_PREFIX_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": obj_id, "pool_id": PREFIX_POOL_2_NAME},
        )
        assert not update_result.errors
        assert update_result.data
        assert update_result.data["TestMandatoryPrefixUpdate"]["ok"]

        # Retrieve the updated object to confirm the pool changed
        loaded = await NodeManager.get_one(id=obj_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        prefix_rels = await loaded.get_relationship("prefix").get_relationships(db=db)
        assert len(prefix_rels) == 1
        assert prefix_rels[0].source_id == prefix_pool_2.id

    # --- Prefix: create with invalid name ---

    async def test_create_prefix_with_invalid_pool_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_PREFIX_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "site-bad-name", "pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert "Unable to find the pool to generate a node for the relationship 'prefix'" in str(result.errors[0])

    # --- Prefix: update with invalid name ---

    async def test_update_prefix_with_invalid_pool_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ip_dataset: dict[str, Any],
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestMandatoryPrefix", branch=default_branch_scope_class)
        obj = await Node.init(db=db, schema=schema, branch=default_branch_scope_class)
        await obj.new(db=db, name="site-bad-update-prefix", prefix=ip_dataset["net_existing"])
        await obj.save(db=db)

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_PREFIX_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": obj.id, "pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert "Unable to find the pool to generate a node for the relationship 'prefix'" in str(result.errors[0])

    # --- Address: create ---

    async def test_create_address_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, address_pool: CoreIPAddressPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "server-address-by-name", "pool_id": ADDRESS_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestMandatoryAddressCreate"]["ok"]
        assert (
            result.data["TestMandatoryAddressCreate"]["object"]["address"]["properties"]["source"]["id"]
            == address_pool.id
        )

        obj_id = result.data["TestMandatoryAddressCreate"]["object"]["id"]
        loaded = await NodeManager.get_one(id=obj_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        address_rels = await loaded.get_relationship("address").get_relationships(db=db)
        assert len(address_rels) == 1
        assert address_rels[0].source_id == address_pool.id

    # --- Address: update (to different pool) ---

    async def test_update_address_from_pool_by_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        address_pool: CoreIPAddressPool,
        address_pool_2: CoreIPAddressPool,
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        # Create object using pool 1 by name
        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "server-update-addr-pool", "pool_id": ADDRESS_POOL_NAME},
        )
        assert not create_result.errors
        assert create_result.data
        obj_id = create_result.data["TestMandatoryAddressCreate"]["object"]["id"]
        assert (
            create_result.data["TestMandatoryAddressCreate"]["object"]["address"]["properties"]["source"]["id"]
            == address_pool.id
        )

        # Update to use pool 2 by name
        update_result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": obj_id, "pool_id": ADDRESS_POOL_2_NAME},
        )
        assert not update_result.errors
        assert update_result.data
        assert update_result.data["TestMandatoryAddressUpdate"]["ok"]

        # Retrieve the updated object to confirm the pool changed
        loaded = await NodeManager.get_one(id=obj_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        address_rels = await loaded.get_relationship("address").get_relationships(db=db)
        assert len(address_rels) == 1
        assert address_rels[0].source_id == address_pool_2.id

    # --- Address: create with invalid name ---

    async def test_create_address_with_invalid_pool_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "server-bad-name", "pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert "Unable to find the pool to generate a node for the relationship 'address'" in str(result.errors[0])

    # --- Address: update with invalid name ---

    async def test_update_address_with_invalid_pool_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        address_pool: CoreIPAddressPool,
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        # Create a valid address object first
        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "server-bad-update-addr", "pool_id": address_pool.id},
        )
        assert not create_result.errors
        assert create_result.data
        obj_id = create_result.data["TestMandatoryAddressCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_ADDRESS_FROM_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": obj_id, "pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert "Unable to find the pool to generate a node for the relationship 'address'" in str(result.errors[0])


# --- Template mutations ---

CREATE_TEMPLATE_PREFIX_WITH_POOL = """
mutation CreateTemplatePrefixWithPool($template_name: String!, $pool_id: String!) {
    TemplateTestMandatoryPrefixCreate(data: {
        template_name: { value: $template_name }
        prefix_from_resource_pool: { id: $pool_id }
    }) {
        ok
        object {
            id
        }
    }
}
"""

CREATE_TEMPLATE_PREFIX_SETUP = """
mutation CreateTemplatePrefixSetup($template_name: String!) {
    TemplateTestMandatoryPrefixCreate(data: {
        template_name: { value: $template_name }
    }) {
        ok
        object {
            id
        }
    }
}
"""

UPDATE_TEMPLATE_PREFIX_POOL = """
mutation UpdateTemplatePrefixPool($id: String!, $pool_id: String!) {
    TemplateTestMandatoryPrefixUpdate(data: {
        id: $id
        prefix_from_resource_pool: { id: $pool_id }
    }) {
        ok
    }
}
"""

CREATE_TEMPLATE_ADDRESS_WITH_POOL = """
mutation CreateTemplateAddressWithPool($template_name: String!, $pool_id: String!) {
    TemplateTestMandatoryAddressCreate(data: {
        template_name: { value: $template_name }
        address_from_resource_pool: { id: $pool_id }
    }) {
        ok
        object {
            id
        }
    }
}
"""

CREATE_TEMPLATE_ADDRESS_SETUP = """
mutation CreateTemplateAddressSetup($template_name: String!) {
    TemplateTestMandatoryAddressCreate(data: {
        template_name: { value: $template_name }
    }) {
        ok
        object {
            id
        }
    }
}
"""

UPDATE_TEMPLATE_ADDRESS_POOL = """
mutation UpdateTemplateAddressPool($id: String!, $pool_id: String!) {
    TemplateTestMandatoryAddressUpdate(data: {
        id: $id
        address_from_resource_pool: { id: $pool_id }
    }) {
        ok
    }
}
"""


class TestIPPoolTemplate:
    """Tests for creating/updating template instances with IP pools by name and by ID."""

    @pytest.fixture(scope="class")
    async def register_ipam_schema(self, default_branch_scope_class: Branch, ipam_schema: SchemaRoot) -> SchemaBranch:
        schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    async def register_ipam_extended_schema(
        self, default_branch_scope_class: Branch, register_ipam_schema: SchemaBranch
    ) -> SchemaBranch:
        SCHEMA = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="MandatoryPrefix",
                    namespace="Test",
                    generate_template=True,
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="prefix",
                            peer="IpamIPPrefix",
                            kind=RelationshipKind.ATTRIBUTE,
                            optional=False,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
                NodeSchema(
                    name="MandatoryAddress",
                    namespace="Test",
                    generate_template=True,
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="address",
                            peer="IpamIPAddress",
                            kind=RelationshipKind.ATTRIBUTE,
                            optional=False,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
            ],
        )
        schema_branch = registry.schema.register_schema(schema=SCHEMA, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    def init_nodes_registry(self) -> None:
        registry.node["Node"] = Node
        registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
        registry.node[InfrahubKind.IPPREFIXPOOL] = CoreIPPrefixPool
        registry.node[InfrahubKind.IPADDRESSPOOL] = CoreIPAddressPool

    @pytest.fixture(scope="class")
    async def default_ipnamespace(
        self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch
    ) -> None:
        if not registry._default_ipnamespace:
            ip_namespace = await create_ipam_namespace(db=db)
            registry.default_ipnamespace = ip_namespace.id

    @pytest.fixture(scope="class")
    async def ip_dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_ipnamespace: None,
        register_ipam_extended_schema: SchemaBranch,
        init_nodes_registry: None,
    ) -> dict[str, Any]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch_scope_class)

        ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns1.new(db=db, name="ns-template")
        await ns1.save(db=db)

        net_parent = await Node.init(db=db, schema=prefix_schema)
        await net_parent.new(db=db, prefix="10.30.0.0/16", ip_namespace=ns1)
        await net_parent.save(db=db)

        net_for_address = await Node.init(db=db, schema=prefix_schema)
        await net_for_address.new(db=db, prefix="10.30.3.0/27", parent=net_parent, ip_namespace=ns1)
        await net_for_address.save(db=db)

        return {"ns1": ns1, "net_parent": net_parent, "net_for_address": net_for_address}

    @pytest.fixture(scope="class")
    async def prefix_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPPrefixPool:
        prefix_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPPREFIXPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=TPL_PREFIX_POOL_NAME,
            default_prefix_length=24,
            default_prefix_type="IpamIPPrefix",
            resources=[ip_dataset["net_parent"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def address_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_dataset: dict[str, Any]
    ) -> CoreIPAddressPool:
        address_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPADDRESSPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch_scope_class)
        await pool.new(
            db=db,
            name=TPL_ADDRESS_POOL_NAME,
            default_address_type="IpamIPAddress",
            resources=[ip_dataset["net_for_address"]],
            ip_namespace=ip_dataset["ns1"],
        )
        await pool.save(db=db)
        return pool

    # --- Prefix template: create ---

    async def test_create_prefix_template_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, prefix_pool: CoreIPPrefixPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_PREFIX_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-prefix-by-name", "pool_id": TPL_PREFIX_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryPrefixCreate"]["ok"]
        template_id = result.data["TemplateTestMandatoryPrefixCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("prefix_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == prefix_pool.id

    async def test_create_prefix_template_from_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, prefix_pool: CoreIPPrefixPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_PREFIX_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-prefix-by-id", "pool_id": prefix_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryPrefixCreate"]["ok"]
        template_id = result.data["TemplateTestMandatoryPrefixCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("prefix_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == prefix_pool.id

    # --- Prefix template: update ---

    async def test_update_prefix_template_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, prefix_pool: CoreIPPrefixPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_PREFIX_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-prefix-update-by-name"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestMandatoryPrefixCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_PREFIX_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template_id, "pool_id": TPL_PREFIX_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryPrefixUpdate"]["ok"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("prefix_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == prefix_pool.id

    async def test_update_prefix_template_from_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, prefix_pool: CoreIPPrefixPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_PREFIX_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-prefix-update-by-id"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestMandatoryPrefixCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_PREFIX_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template_id, "pool_id": prefix_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryPrefixUpdate"]["ok"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("prefix_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == prefix_pool.id

    # --- Address template: create ---

    async def test_create_address_template_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, address_pool: CoreIPAddressPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_ADDRESS_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-address-by-name", "pool_id": TPL_ADDRESS_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryAddressCreate"]["ok"]
        template_id = result.data["TemplateTestMandatoryAddressCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("address_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == address_pool.id

    async def test_create_address_template_from_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, address_pool: CoreIPAddressPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_ADDRESS_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-address-by-id", "pool_id": address_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryAddressCreate"]["ok"]
        template_id = result.data["TemplateTestMandatoryAddressCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("address_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == address_pool.id

    # --- Address template: update ---

    async def test_update_address_template_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, address_pool: CoreIPAddressPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_ADDRESS_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-address-update-by-name"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestMandatoryAddressCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_ADDRESS_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template_id, "pool_id": TPL_ADDRESS_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryAddressUpdate"]["ok"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("address_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == address_pool.id

    async def test_update_address_template_from_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, address_pool: CoreIPAddressPool
    ) -> None:
        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_ADDRESS_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-address-update-by-id"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestMandatoryAddressCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_ADDRESS_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template_id, "pool_id": address_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestMandatoryAddressUpdate"]["ok"]

        loaded = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        assert loaded is not None
        pool_peer = await loaded.get_relationship("address_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == address_pool.id
