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
from infrahub.core.schema import SchemaRoot
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

TRIGGER_PLACEHOLDER = "_trigger_placeholder"


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
        assert len(self_triggers) == 1, "Expected exactly one self-targeting trigger"

        trigger_def = self_triggers[0]
        assert trigger_def.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER], (
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
        color__description__value. It should NOT use placeholder fields."""
        triggers = await gather_trigger_computed_attribute_jinja2(db=db)

        remote_triggers = [t for t in triggers if not t.targets_self]
        assert len(remote_triggers) == 1, "Expected exactly one remote trigger"

        trigger_def = remote_triggers[0]
        fields = trigger_def.trigger.match_related["infrahub.field.name"]
        assert TRIGGER_PLACEHOLDER not in fields, (
            f"Remote trigger for {trigger_def.trigger_kind} should NOT use placeholder fields, got {fields}"
        )
        assert sorted(fields) == ["description", "name"], (
            f"Remote trigger should match 'name' and 'description' fields, got {fields}"
        )
