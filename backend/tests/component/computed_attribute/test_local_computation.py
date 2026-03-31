from unittest.mock import AsyncMock, patch

import pytest
from infrahub_sdk.template.exceptions import JinjaTemplateError

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema_with_jinja2(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Schema with all four flavours of Jinja2 computed attributes:
    - local_label: mandatory, depends on local attrs (name, role)
    - local_tag: optional, depends on local attrs (name, role)
    - remote_label: mandatory, depends on peer attr (owner.name) + local attr (name)
    - remote_tag: optional, depends on peer attr (owner.name) + local attr (role)
    Plus an unrelated attribute (description) for negative tests.
    """
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="ComputeOwner",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                ],
            ),
            NodeSchema(
                name="ComputeDevice",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="role", kind="Text"),
                    AttributeSchema(name="description", kind="Text", optional=True),
                    AttributeSchema(
                        name="local_label",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }}-{{ role__value }}",
                        ),
                    ),
                    AttributeSchema(
                        name="local_tag",
                        kind="Text",
                        optional=True,
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ role__value }}:{{ name__value }}",
                        ),
                    ),
                    AttributeSchema(
                        name="remote_label",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ owner__name__value }}'s {{ name__value }}",
                        ),
                    ),
                    AttributeSchema(
                        name="remote_tag",
                        kind="Text",
                        optional=True,
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ owner__name__value }}-{{ role__value }}",
                        ),
                    ),
                ],
                relationships=[
                    RelationshipSchema(
                        name="owner",
                        peer="TestComputeOwner",
                        optional=False,
                        cardinality=RelationshipCardinality.ONE,
                    ),
                ],
            ),
        ]
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)


@pytest.fixture
async def schema_with_chained_jinja2(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Two computed attributes where fqdn depends on label (chained computation)."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="ComputeServer",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="role", kind="Text"),
                    AttributeSchema(
                        name="label",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }}-{{ role__value }}",
                        ),
                    ),
                    AttributeSchema(
                        name="fqdn",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ label__value }}.example.com",
                        ),
                    ),
                ],
            ),
        ]
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)


async def _create_owner(db: InfrahubDatabase, default_branch: Branch, name: str = "Alice") -> Node:
    owner = await Node.init(db=db, schema="TestComputeOwner", branch=default_branch)
    await owner.new(db=db, name=name)
    await owner.save(db=db)
    return owner


async def _create_device(
    db: InfrahubDatabase, default_branch: Branch, owner: Node, name: str = "switch01", role: str = "spine"
) -> Node:
    device = await Node.init(db=db, schema="TestComputeDevice", branch=default_branch)
    await device.new(db=db, name=name, role=role, owner=owner)
    await device.save(db=db)
    return device


async def test_all_jinja2_flavours_computed_at_creation(
    db: InfrahubDatabase, default_branch: Branch, schema_with_jinja2: None
) -> None:
    """All four Jinja2 computed attributes are evaluated inline during creation."""
    owner = await _create_owner(db=db, default_branch=default_branch)
    device = await _create_device(db=db, default_branch=default_branch, owner=owner)

    assert device.get_attribute("local_label").value == "switch01-spine"
    assert device.get_attribute("local_tag").value == "spine:switch01"
    assert device.get_attribute("remote_label").value == "Alice's switch01"
    assert device.get_attribute("remote_tag").value == "Alice-spine"

    reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch)
    assert reloaded.get_attribute("local_label").value == "switch01-spine"
    assert reloaded.get_attribute("local_tag").value == "spine:switch01"
    assert reloaded.get_attribute("remote_label").value == "Alice's switch01"
    assert reloaded.get_attribute("remote_tag").value == "Alice-spine"


async def test_local_attr_change_triggers_recomputation(
    db: InfrahubDatabase, default_branch: Branch, schema_with_jinja2: None
) -> None:
    """Updating a local attribute recomputes all computed attributes that depend on it."""
    owner = await _create_owner(db=db, default_branch=default_branch)
    device = await _create_device(db=db, default_branch=default_branch, owner=owner)

    device.get_attribute("name").value = "switch02"
    await device.save(db=db, fields=["name"])

    # local_label and local_tag depend on name
    assert device.get_attribute("local_label").value == "switch02-spine"
    assert device.get_attribute("local_tag").value == "spine:switch02"
    # remote_label depends on name too
    assert device.get_attribute("remote_label").value == "Alice's switch02"
    # remote_tag depends on role, not name — unchanged
    assert device.get_attribute("remote_tag").value == "Alice-spine"

    reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch)
    assert reloaded.get_attribute("local_label").value == "switch02-spine"
    assert reloaded.get_attribute("local_tag").value == "spine:switch02"
    assert reloaded.get_attribute("remote_label").value == "Alice's switch02"


async def test_unrelated_attr_change_does_not_trigger_recomputation(
    db: InfrahubDatabase, default_branch: Branch, schema_with_jinja2: None
) -> None:
    """Updating an attribute not referenced by any template does NOT trigger recomputation."""
    owner = await _create_owner(db=db, default_branch=default_branch)
    device = await _create_device(db=db, default_branch=default_branch, owner=owner, name="switch01", role="spine")

    with patch.object(
        InfrahubJinja2Template,
        "render",
        new_callable=AsyncMock,
    ) as mock_render:
        device.get_attribute("description").value = "updated"
        await device.save(db=db, fields=["description"])
        mock_render.assert_not_called()

    assert device.get_attribute("local_label").value == "switch01-spine"


async def test_chained_jinja2_cascade(
    db: InfrahubDatabase, default_branch: Branch, schema_with_chained_jinja2: None
) -> None:
    """Chained computed attributes cascade: name -> label -> fqdn all recomputed inline."""
    server = await Node.init(db=db, schema="TestComputeServer", branch=default_branch)
    await server.new(db=db, name="web01", role="frontend")
    await server.save(db=db)

    assert server.get_attribute("label").value == "web01-frontend"
    assert server.get_attribute("fqdn").value == "web01-frontend.example.com"

    server.get_attribute("name").value = "web02"
    await server.save(db=db, fields=["name"])

    assert server.get_attribute("label").value == "web02-frontend"
    assert server.get_attribute("fqdn").value == "web02-frontend.example.com"

    reloaded = await NodeManager.get_one(db=db, id=server.id, branch=default_branch)
    assert reloaded.get_attribute("fqdn").value == "web02-frontend.example.com"


async def test_jinja2_error_handled_gracefully(
    db: InfrahubDatabase, default_branch: Branch, schema_with_jinja2: None
) -> None:
    """A Jinja2 evaluation failure is logged but the mutation succeeds."""
    owner = await _create_owner(db=db, default_branch=default_branch)
    device = await _create_device(db=db, default_branch=default_branch, owner=owner, name="gear01", role="red")

    assert device.get_attribute("local_label").value == "gear01-red"

    with patch(
        "infrahub.core.node.InfrahubJinja2Template.render",
        new_callable=AsyncMock,
        side_effect=JinjaTemplateError(message="Simulated Jinja2 rendering failure"),
    ):
        device.get_attribute("name").value = "gear02"
        await device.save(db=db, fields=["name"])

    assert device.get_attribute("name").value == "gear02"
    assert device.get_attribute("local_label").value == "gear01-red"
