from unittest.mock import AsyncMock, patch

import pytest

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    SchemaRoot,
)
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema_with_local_jinja2(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Single computed attribute (label) derived from two local attributes (name, role)."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="ComputeDevice",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="role", kind="Text"),
                    AttributeSchema(name="description", kind="Text", optional=True),
                    AttributeSchema(
                        name="label",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }}-{{ role__value }}",
                        ),
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


@pytest.fixture
async def schema_with_render_test(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    """Simple computed attribute used to test graceful handling of Jinja2 render errors."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="ComputeWidget",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="color", kind="Text"),
                    AttributeSchema(
                        name="computed_label",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }}-{{ color__value }}",
                        ),
                    ),
                ],
            ),
        ]
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)


async def test_local_attr_change_triggers_recomputation(
    db: InfrahubDatabase, default_branch: Branch, schema_with_local_jinja2: None
) -> None:
    """Updating a referenced attribute triggers inline Jinja2 recomputation."""
    device = await Node.init(db=db, schema="TestComputeDevice", branch=default_branch)
    await device.new(db=db, name="switch01", role="spine")
    await device.save(db=db)

    assert device.get_attribute("label").value == "switch01-spine"

    device.get_attribute("name").value = "switch02"

    # Act
    await device.save(db=db, fields=["name"])

    # Assert local computation
    assert device.get_attribute("label").value == "switch02-spine"

    # Assert saved in the database
    reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch)
    assert reloaded.get_attribute("label").value == "switch02-spine"


async def test_unrelated_attr_change_does_not_trigger_recomputation(
    db: InfrahubDatabase, default_branch: Branch, schema_with_local_jinja2: None
) -> None:
    """Updating an attribute not referenced by the template does NOT trigger recomputation."""
    device = await Node.init(db=db, schema="TestComputeDevice", branch=default_branch)
    await device.new(db=db, name="switch01", role="spine", description="original")
    await device.save(db=db)

    # Save only an unrelated attribute and verify no Jinja2 render occurs
    with patch.object(
        InfrahubJinja2Template, "render",
        new_callable=AsyncMock,
    ) as mock_render:
        device.get_attribute("description").value = "updated"
        await device.save(db=db, fields=["description"])
        mock_render.assert_not_called()
    assert device.get_attribute("label").value == "switch01-spine"


async def test_chained_jinja2_only_direct_deps_recomputed_inline(
    db: InfrahubDatabase, default_branch: Branch, schema_with_chained_jinja2: None
) -> None:
    """Only direct dependencies are recomputed inline; chained deps are left to the event system."""
    server = await Node.init(db=db, schema="TestComputeServer", branch=default_branch)
    await server.new(db=db, name="web01", role="frontend")
    await server.save(db=db)

    assert server.get_attribute("label").value == "web01-frontend"
    assert server.get_attribute("fqdn").value == "web01-frontend.example.com"

    # Update name — label (direct dep of name) recomputes inline,
    # but fqdn (depends on label, not name) is left for async event cascade.
    server.get_attribute("name").value = "web02"

    # Act
    await server.save(db=db, fields=["name"])

    assert server.get_attribute("label").value == "web02-frontend"
    # fqdn still has old value — it will be updated by the async event path
    assert server.get_attribute("fqdn").value == "web01-frontend.example.com"


async def test_jinja2_error_handled_gracefully(
    db: InfrahubDatabase, default_branch: Branch, schema_with_render_test: None
) -> None:
    """A Jinja2 evaluation failure is logged but the mutation succeeds."""
    widget = await Node.init(db=db, schema="TestComputeWidget", branch=default_branch)
    await widget.new(db=db, name="gear01", color="red")
    await widget.save(db=db)

    assert widget.get_attribute("computed_label").value == "gear01-red"

    with patch(
        "infrahub.core.node.InfrahubJinja2Template.render",
        new_callable=AsyncMock,
        side_effect=Exception("Simulated Jinja2 rendering failure"),
    ):
        widget.get_attribute("name").value = "gear02"
        await widget.save(db=db, fields=["name"])

    assert widget.get_attribute("name").value == "gear02"
    assert widget.get_attribute("computed_label").value == "gear01-red"
