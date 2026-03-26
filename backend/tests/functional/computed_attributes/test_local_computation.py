"""Functional tests for local computation of Jinja2 computed attributes.

Verifies that:
- Self-targeting triggers use _trigger_placeholder fields
- Remote triggers preserve real field names and would still fire for peer changes
- The gather function produces the correct trigger structure for mixed dependencies
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.gather import gather_trigger_computed_attribute_jinja2
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestGatherJinja2Triggers(TestInfrahubApp):
    """Verify that gather_trigger_computed_attribute_jinja2 produces the correct
    trigger structure: placeholder fields for self-targeting, real fields for remote."""

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
        (TestingTShirt) should use _trigger_placeholder fields."""
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        self_triggers = [t for t in triggers if t.targets_self]
        assert len(self_triggers) >= 1, "Expected at least one self-targeting trigger"

        for trigger in self_triggers:
            assert trigger.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER_FIELD], (
                f"Self-targeting trigger for {trigger.trigger_kind} should use placeholder fields, "
                f"got {trigger.trigger.match_related['infrahub.field.name']}"
            )

    async def test_remote_trigger_has_real_fields(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """The remote trigger (TestingColor) should preserve real field names so that
        peer attribute changes (e.g. renaming a Color) still fire background tasks."""
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        remote_triggers = [t for t in triggers if not t.targets_self]
        assert len(remote_triggers) >= 1, "Expected at least one remote trigger"

        for trigger in remote_triggers:
            fields = trigger.trigger.match_related["infrahub.field.name"]
            assert TRIGGER_PLACEHOLDER_FIELD not in fields, (
                f"Remote trigger for {trigger.trigger_kind} should NOT use placeholder fields, got {fields}"
            )
            assert len(fields) > 0, f"Remote trigger for {trigger.trigger_kind} should have real field names"

    async def test_remote_trigger_matches_peer_attribute_changes(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """Verify the remote trigger for TestingColor includes 'name' and 'description'
        as fields, since the Jinja2 template references color__name__value and
        color__description__value."""
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        color_triggers = [t for t in triggers if t.trigger_kind == "TestingColor"]
        assert len(color_triggers) == 1, f"Expected exactly 1 TestingColor trigger, got {len(color_triggers)}"

        fields = color_triggers[0].trigger.match_related["infrahub.field.name"]
        assert "name" in fields, f"TestingColor trigger should include 'name' field, got {fields}"
        assert "description" in fields, f"TestingColor trigger should include 'description' field, got {fields}"

    async def test_remote_change_triggers_recomputation(
        self,
        db: InfrahubDatabase,
        schema_loaded: None,
        default_branch: Branch,
    ) -> None:
        """Create a TShirt with a Color, then update the Color's name. Verify that the
        trigger structure would match this change (the remote trigger includes the 'name' field
        for TestingColor and the event match targets TestingColor kind)."""
        c1 = await Node.init(db=db, schema="TestingColor")
        await c1.new(db=db, name="Crimson", description="A deep, rich red.")
        await c1.save(db=db)

        t1 = await Node.init(db=db, schema="TestingTShirt")
        await t1.new(db=db, name="Flame", color=c1)
        await t1.save(db=db)

        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        color_triggers = [t for t in triggers if t.trigger_kind == "TestingColor"]
        assert len(color_triggers) >= 1

        color_trigger = color_triggers[0]
        # The trigger should match NodeUpdatedEvent for TestingColor
        assert color_trigger.trigger.match["infrahub.node.kind"] == "TestingColor"
        # The trigger should match on the 'name' field being updated
        assert "name" in color_trigger.trigger.match_related["infrahub.field.name"]
        # The trigger should NOT use placeholder fields
        assert TRIGGER_PLACEHOLDER_FIELD not in color_trigger.trigger.match_related["infrahub.field.name"]
