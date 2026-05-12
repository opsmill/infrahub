"""Functional tests for local computation of Jinja2 computed attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.gather import gather_trigger_computed_attribute_jinja2
from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestJinja2ComputedAttributeWithRelationship(TestInfrahubApp):
    """Verify trigger structure and runtime recomputation for Jinja2 computed attributes
    that reference relationship peers (using the TSHIRT/COLOR schema).
    """

    @pytest.fixture(scope="class")
    async def schema_loaded(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
    ) -> None:
        await load_schema(db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]), update_db=True)

    async def test_self_targeting_trigger_has_placeholder_fields(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """The TSHIRT schema has a Jinja2 computed 'description' that references both
        local attribute 'name' and peer attribute 'color__name'. The self-targeting trigger
        (TestingTShirt) should use _trigger_placeholder fields.
        """
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        self_triggers = [t for t in triggers if t.targets_self]
        assert len(self_triggers) == 1, "Expected exactly one self-targeting trigger"

        trigger_def = self_triggers[0]
        assert isinstance(trigger_def.trigger.match_related, dict)
        assert trigger_def.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER_FIELD], (
            f"Self-targeting trigger for {trigger_def.trigger_kind} should use placeholder fields, "
            f"got {trigger_def.trigger.match_related['infrahub.field.name']}"
        )

    async def test_remote_trigger_preserves_real_fields(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """The remote trigger (TestingColor) should preserve real field names ('name' and
        'description') since the Jinja2 template references color__name__value and
        color__description__value. It should NOT use placeholder fields.
        """
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        remote_triggers = [t for t in triggers if not t.targets_self]
        assert len(remote_triggers) == 1, "Expected exactly one remote trigger"

        trigger_def = remote_triggers[0]
        assert isinstance(trigger_def.trigger.match_related, dict)
        fields = trigger_def.trigger.match_related["infrahub.field.name"]
        assert TRIGGER_PLACEHOLDER_FIELD not in fields, (
            f"Remote trigger for {trigger_def.trigger_kind} should NOT use placeholder fields, got {fields}"
        )
        assert sorted(fields) == ["color", "description", "name"], (
            f"Remote trigger should match 'color', 'name' and 'description' fields, got {fields}"
        )

    async def test_relationship_change_triggers_recomputation(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """Changing a TShirt's color relationship recomputes the description
        to reflect the new peer's attributes.
        """
        color_red = await Node.init(db=db, schema="TestingColor", branch=default_branch)
        await color_red.new(db=db, name="Red", description="Bright red")
        await color_red.save(db=db)

        color_blue = await Node.init(db=db, schema="TestingColor", branch=default_branch)
        await color_blue.new(db=db, name="Blue", description="Ocean blue")
        await color_blue.save(db=db)

        tshirt = await Node.init(db=db, schema="TestingTShirt", branch=default_branch)
        await tshirt.new(db=db, name="Classic", color=color_red)
        await tshirt.save(db=db)

        assert tshirt.get_attribute("description").value == "A Red Classic t-shirt. Bright red"

        # Update the color relationship to Blue
        await tshirt.color.update(data=color_blue, db=db)
        await tshirt.save(db=db, fields=["color"])

        assert tshirt.get_attribute("description").value == "A Blue Classic t-shirt. Ocean blue"

        # Verify persisted in DB
        reloaded = await NodeManager.get_one(db=db, id=tshirt.id, branch=default_branch)
        assert reloaded.get_attribute("description").value == "A Blue Classic t-shirt. Ocean blue"


class TestNullRelationshipRecomputation(TestInfrahubApp):
    """Verify that setting a relationship to null renders the template with null context."""

    @pytest.fixture(scope="class")
    async def schema_loaded(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
    ) -> None:
        site_schema = NodeSchema(
            name="Site",
            namespace="Testcomp",
            default_filter="name__value",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
            ],
        )
        device_schema = NodeSchema(
            name="Device",
            namespace="Testcomp",
            default_filter="name__value",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(
                    name="label",
                    kind="Text",
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ site__name__value }}-{{ name__value }}",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="site",
                    peer="TestcompSite",
                    optional=True,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        )
        await load_schema(db, schema=SchemaRoot(nodes=[site_schema, device_schema]), update_db=True)

    async def test_null_relationship_renders_template(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """Setting an optional relationship to null renders the template with None for the peer variable."""
        site = await Node.init(db=db, schema="TestcompSite", branch=default_branch)
        await site.new(db=db, name="DC1")
        await site.save(db=db)

        device = await Node.init(db=db, schema="TestcompDevice", branch=default_branch)
        await device.new(db=db, name="switch01", site=site)
        await device.save(db=db)

        assert device.get_attribute("label").value == "DC1-switch01"

        # Set relationship to null
        await device.site.update(data=None, db=db)
        await device.save(db=db, fields=["site"])

        assert device.get_attribute("label").value == "None-switch01"

        # Verify persisted in DB
        reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch)
        assert reloaded.get_attribute("label").value == "None-switch01"


class TestEventConsolidation(TestInfrahubApp):
    """Verify single changelog per mutation contains both original and computed attribute changes.

    The _recompute_local_jinja2() method records computed attribute changes in the same
    NodeChangelog as the original mutation. generate_node_mutation_events() reads
    node.node_changelog.updated_fields to emit a single event covering both fields.
    """

    @pytest.fixture(scope="class")
    async def schema_loaded(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
    ) -> None:
        await load_schema(db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]), update_db=True)

    @pytest.fixture(scope="class")
    async def color_node(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> Node:
        color = await Node.init(db=db, schema="TestingColor", branch=default_branch)
        await color.new(db=db, name="Green", description="Forest green")
        await color.save(db=db)
        return color

    async def test_single_changelog_contains_both_original_and_computed_fields(
        self,
        db: InfrahubDatabase,
        color_node: Node,
        default_branch: Branch,
    ) -> None:
        """Updating a local attribute that triggers Jinja2 recomputation produces a single
        NodeChangelog with both the original attribute and the computed attribute in updated_fields.
        """
        tshirt = await Node.init(db=db, schema="TestingTShirt", branch=default_branch)
        await tshirt.new(db=db, name="Classic", color=color_node)
        await tshirt.save(db=db)

        assert tshirt.get_attribute("description").value == "A Green Classic t-shirt. Forest green"

        # Update the name attribute
        tshirt.get_attribute("name").value = "Premium"
        await tshirt.save(db=db)

        # The computed 'description' should have been recomputed inline
        assert tshirt.get_attribute("description").value == "A Green Premium t-shirt. Forest green"

        # Verify the changelog records BOTH the original and computed attribute changes
        changelog = tshirt.node_changelog
        updated = changelog.updated_fields
        assert "name" in updated, f"Expected 'name' in updated_fields, got {updated}"
        assert "description" in updated, f"Expected 'description' in updated_fields, got {updated}"

        # Verify there is exactly one changelog containing both changes
        assert changelog.has_changes
        assert "name" in changelog.attributes
        assert "description" in changelog.attributes

        # Verify persisted in DB
        reloaded = await NodeManager.get_one(db=db, id=tshirt.id, branch=default_branch)
        assert reloaded.get_attribute("description").value == "A Green Premium t-shirt. Forest green"

    async def test_no_spurious_computed_changelog_when_value_unchanged(
        self,
        db: InfrahubDatabase,
        color_node: Node,
        default_branch: Branch,
    ) -> None:
        """If an update does not change the computed attribute value, it should NOT appear
        in the changelog (no-op recomputation is filtered out).
        """
        tshirt = await Node.init(db=db, schema="TestingTShirt", branch=default_branch)
        await tshirt.new(db=db, name="Basic", color=color_node)
        await tshirt.save(db=db)

        assert tshirt.get_attribute("description").value == "A Green Basic t-shirt. Forest green"

        # Update name to the same value (no change)
        tshirt.get_attribute("name").value = "Basic"
        await tshirt.save(db=db)

        # The description should still be the same
        assert tshirt.get_attribute("description").value == "A Green Basic t-shirt. Forest green"

        # Since neither name nor description actually changed value, the changelog
        # should NOT contain 'description' (the recomputation produced the same value)
        changelog = tshirt.node_changelog
        assert "description" not in changelog.attributes, (
            f"Computed attribute 'description' should not be in changelog when value is unchanged, "
            f"got updated_fields={changelog.updated_fields}"
        )
