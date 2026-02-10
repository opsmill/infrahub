from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.pools.allocator import PoolAllocator
from infrahub.pools.default_allocator import DefaultPoolAllocator
from infrahub.templates.node_applier import NodeTemplateApplier
from tests.constants import TestKind
from tests.helpers.schema import TAG, load_schema
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class NoOpPoolAllocator(PoolAllocator):
    """Test pool allocator that skips all allocations (because we don't care here)."""

    async def allocate_for_attribute(self, *args: Any, **kwargs: Any) -> Any | None:
        return None

    async def allocate_for_relationship(self, *args: Any, **kwargs: Any) -> Node | None:
        return None


@dataclass
class ExpectedTemplateAttr:
    """Expected attribute value and source from template application."""

    name: str
    value: Any
    source_id: str


@dataclass
class ExpectedTemplateRelationship:
    """Expected relationship peers from template application."""

    name: str
    peer_ids: list[str]


def _validate_template_fields(
    fields: dict[str, Any],
    expected_attrs: list[ExpectedTemplateAttr] | None = None,
    expected_relationships: list[ExpectedTemplateRelationship] | None = None,
    user_fields: dict[str, Any] | None = None,
) -> None:
    """Validate that template application produced expected fields.

    Args:
        fields: The fields dict returned by NodeTemplateApplier.apply()
        expected_attrs: List of expected attribute values with sources
        expected_relationships: List of expected relationship peers
        user_fields: Original user fields (should be preserved as-is)
    """
    user_fields = user_fields or {}
    expected_attrs = expected_attrs or []
    expected_relationships = expected_relationships or []

    # Validate user fields are preserved exactly
    for field_name, field_value in user_fields.items():
        assert fields[field_name] == field_value, f"User field {field_name} was not preserved"

    # Validate expected template attributes
    for attr in expected_attrs:
        assert attr.name in fields, f"Expected attribute {attr.name} not in fields"
        field_data = fields[attr.name]
        assert isinstance(field_data, dict), f"Template attribute {attr.name} should be a dict with value/source"
        assert field_data["value"] == attr.value, f"Attribute {attr.name} has wrong value"
        assert field_data["source"] == attr.source_id, f"Attribute {attr.name} has wrong source"

    # Validate expected relationships
    for rel in expected_relationships:
        assert rel.name in fields, f"Expected relationship {rel.name} not in fields"
        field_data = fields[rel.name]
        if isinstance(field_data, list):
            actual_ids = [item["id"] for item in field_data]
            assert actual_ids == rel.peer_ids, f"Relationship {rel.name} has wrong peer IDs"
        else:
            assert field_data == {"id": rel.peer_ids[0]}, f"Relationship {rel.name} has wrong peer"


@pytest.fixture
async def device_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, init_nodes_registry: None
) -> None:
    """Device schema with tag relationships for template testing."""
    device = copy.deepcopy(DEVICE)
    device.relationships = [
        RelationshipSchema(
            name="primary_tag",
            peer=TestKind.TAG,
            identifier="device__primary_tag",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
        RelationshipSchema(
            name="tags",
            peer=TestKind.TAG,
            identifier="device__tags",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        ),
    ]
    schema = SchemaRoot(generics=[INTERFACE_HOLDER, INTERFACE], nodes=[device, TAG])
    await load_schema(db=db, schema=schema)


@pytest.fixture
async def device_template(db: InfrahubDatabase, default_branch: Branch, device_schema: None) -> Node:
    """A device template with manufacturer and height values set."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(db=db, template_name="device-template", manufacturer="Acme", height=42)
    await template.save(db=db)
    return template


@pytest.fixture
async def tag_node(db: InfrahubDatabase, default_branch: Branch, device_schema: None) -> Node:
    tag_schema = registry.schema.get_node_schema(name=TestKind.TAG, branch=default_branch)
    tag = await Node.init(schema=tag_schema, db=db, branch=default_branch)
    await tag.new(db=db, name="important")
    await tag.save(db=db)
    return tag


@pytest.fixture
async def second_tag_node(db: InfrahubDatabase, default_branch: Branch, device_schema: None) -> Node:
    tag_schema = registry.schema.get_node_schema(name=TestKind.TAG, branch=default_branch)
    tag = await Node.init(schema=tag_schema, db=db, branch=default_branch)
    await tag.new(db=db, name="secondary")
    await tag.save(db=db)
    return tag


class TestNodeTemplateApplierAttributes:
    async def test_applies_attribute_values_from_template(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, device_template: Node
    ) -> None:
        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=device_template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[
                ExpectedTemplateAttr(name="manufacturer", value="Acme", source_id=device_template.id),
                ExpectedTemplateAttr(name="height", value=42, source_id=device_template.id),
            ],
            user_fields=user_fields,
        )
        assert "template_name" not in fields

    async def test_user_fields_take_precedence(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, device_template: Node
    ) -> None:
        """User-provided fields should not be overridden by template values."""
        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "manufacturer": "User Corp", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=device_template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[ExpectedTemplateAttr(name="height", value=42, source_id=device_template.id)],
            user_fields=user_fields,
        )

    async def test_skips_none_template_values(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        """Template attributes with None values should not be included in output fields."""
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(db=db, template_name="sparse-template", manufacturer="OnlyManufacturer")
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[
                ExpectedTemplateAttr(name="manufacturer", value="OnlyManufacturer", source_id=template.id),
                ExpectedTemplateAttr(name="height", value=1, source_id=template.id),
            ],
            user_fields=user_fields,
        )
        assert "part_number" not in fields


class TestNodeTemplateApplierRelationships:
    async def test_applies_cardinality_one_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, tag_node: Node
    ) -> None:
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(
            db=db, template_name="template-with-tag", manufacturer="Acme", primary_tag={"id": tag_node.id}
        )
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[ExpectedTemplateAttr(name="manufacturer", value="Acme", source_id=template.id)],
            expected_relationships=[ExpectedTemplateRelationship(name="primary_tag", peer_ids=[tag_node.id])],
            user_fields=user_fields,
        )

    async def test_applies_cardinality_many_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, tag_node: Node, second_tag_node: Node
    ) -> None:
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(
            db=db,
            template_name="template-with-tags",
            manufacturer="Acme",
            tags=[{"id": tag_node.id}, {"id": second_tag_node.id}],
        )
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[ExpectedTemplateAttr(name="manufacturer", value="Acme", source_id=template.id)],
            expected_relationships=[
                ExpectedTemplateRelationship(name="tags", peer_ids=[tag_node.id, second_tag_node.id])
            ],
            user_fields=user_fields,
        )

    async def test_user_relationship_takes_precedence(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, tag_node: Node, second_tag_node: Node
    ) -> None:
        """User-provided relationships should not be overridden by template relationships."""
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(
            db=db, template_name="template-with-tag", manufacturer="Acme", primary_tag={"id": tag_node.id}
        )
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {
            "name": "my-device",
            "weight": 100,
            "airflow": "Front to rear",
            "primary_tag": {"id": second_tag_node.id},
        }

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(
            fields=fields,
            expected_attrs=[ExpectedTemplateAttr(name="manufacturer", value="Acme", source_id=template.id)],
            user_fields=user_fields,
        )

    async def test_empty_relationship_not_included(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        """Template relationships with no peers should not be included in output."""
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(db=db, template_name="template-no-relations", manufacturer="Acme")
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(fields=fields, user_fields=user_fields)
        assert "primary_tag" not in fields
        assert "tags" not in fields


class TestNodeTemplateApplierPoolRelationships:
    @pytest.fixture
    async def pool_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_ipam_schema: SchemaBranch,
        init_nodes_registry: None,
    ) -> None:
        """Device schema with IP address relationship for pool allocation testing."""
        device = copy.deepcopy(DEVICE)
        device.relationships = [
            RelationshipSchema(
                name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
            )
        ]
        schema = SchemaRoot(generics=[INTERFACE_HOLDER, INTERFACE], nodes=[device])
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()

    @pytest.fixture
    async def ip_namespace(self, db: InfrahubDatabase, register_ipam_schema: SchemaBranch) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="test-ns")
        await ns.save(db=db)
        return ns

    @pytest.fixture
    async def ip_prefix(self, db: InfrahubDatabase, default_branch: Branch, ip_namespace: Node) -> Node:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        prefix = await Node.init(db=db, schema=prefix_schema)
        await prefix.new(db=db, prefix="10.0.0.0/24", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture
    async def ip_pool(
        self, db: InfrahubDatabase, default_branch: Branch, ip_namespace: Node, ip_prefix: Node
    ) -> CoreIPAddressPool:
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
        pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
        await pool.new(
            db=db,
            name="test-pool",
            resources=[ip_prefix],
            ip_namespace=ip_namespace,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)
        return pool

    async def test_allocates_from_pool_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, pool_schema: None, ip_pool: CoreIPAddressPool
    ) -> None:
        """Pool relationships should trigger allocation and set source to pool."""
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(db=db, template_name="device-template", primary_ip_from_resource_pool={"id": ip_pool.id})
        await template.save(db=db)

        applier = NodeTemplateApplier(
            db=db, branch=default_branch, pool_allocator=DefaultPoolAllocator(db=db, branch=default_branch)
        )
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(fields=fields, user_fields=user_fields)
        assert "primary_ip" in fields
        assert fields["primary_ip"]["_relation__source"] == ip_pool.id
        assert fields["primary_ip"]["peer"] is not None

    async def test_user_value_overrides_pool_allocation(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        pool_schema: None,
        ip_pool: CoreIPAddressPool,
        ip_namespace: Node,
        ip_prefix: Node,
    ) -> None:
        """User-provided relationship value should prevent pool allocation."""
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
        explicit_ip = await Node.init(db=db, schema=address_schema, branch=default_branch)
        await explicit_ip.new(db=db, address="10.0.0.99/24", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await explicit_ip.save(db=db)

        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(db=db, template_name="device-template", primary_ip_from_resource_pool={"id": ip_pool.id})
        await template.save(db=db)

        applier = NodeTemplateApplier(
            db=db, branch=default_branch, pool_allocator=DefaultPoolAllocator(db=db, branch=default_branch)
        )
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {
            "name": "my-device",
            "weight": 100,
            "airflow": "Front to rear",
            "primary_ip": {"id": explicit_ip.id},
        }

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(fields=fields, user_fields=user_fields)

    async def test_skips_pool_when_noop_allocator(
        self, db: InfrahubDatabase, default_branch: Branch, pool_schema: None, ip_pool: CoreIPAddressPool
    ) -> None:
        """NoOp allocator should skip pool allocation entirely."""
        template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
        template = await Node.init(schema=template_schema, db=db, branch=default_branch)
        await template.new(db=db, template_name="device-template", primary_ip_from_resource_pool={"id": ip_pool.id})
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        target_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
        user_fields = {"name": "my-device", "weight": 100, "airflow": "Front to rear"}

        fields = await applier.apply(
            template=template, target_schema=target_schema, target_id="new-device-id", user_fields=user_fields
        )

        _validate_template_fields(fields=fields, user_fields=user_fields)
        assert "primary_ip" not in fields
