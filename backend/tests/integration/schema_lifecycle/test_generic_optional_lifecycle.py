"""Verify changing the `optional` field on a generic attribute, in both directions, end to end.

The whole lifecycle runs as ordered steps against a single test class (sharing one schema branch
and dataset) and drives schema updates through `client.schema.load` so the real API code path is
exercised:

  step01 - baseline: a generic with a mandatory attribute, inherited by two child nodes
  step02 - mandatory -> optional on the generic propagates to all child nodes
  step03 - optional -> mandatory is blocked while a child instance has a null value
  step04 - optional -> mandatory succeeds once every instance has a value
  step05 - a child node can override the generic's optional setting back to mandatory
  step06 - making an attribute optional is rejected while it is referenced in a human_friendly_id
  step07 - an optional attribute in a human_friendly_id is allowed when it has a default_value
"""

from copy import deepcopy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

GENERIC_KIND = "TestingDevice"
ROUTER_KIND = "TestingRouter"
SWITCH_KIND = "TestingSwitch"
TAGGED_KIND = "TestingTagged"


# Strict mode is disabled globally for the suite, but this test asserts the strict-mode-only
# hfid/uniqueness guard (step06/step07), so it opts back into strict mode.
@pytest.mark.usefixtures("enable_schema_strict_mode_class")
class TestSchemaLifecycleGenericOptional(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_generic_device(self) -> dict[str, Any]:
        """Generic with a mandatory asset_tag attribute."""
        return {
            "name": "Device",
            "namespace": "Testing",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "asset_tag", "kind": "Text", "optional": False},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_router(self) -> dict[str, Any]:
        return {"name": "Router", "namespace": "Testing", "inherit_from": [GENERIC_KIND]}

    @pytest.fixture(scope="class")
    def schema_switch(self) -> dict[str, Any]:
        return {"name": "Switch", "namespace": "Testing", "inherit_from": [GENERIC_KIND]}

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_device],
            "nodes": [schema_router, schema_switch],
        }

    def _schema_with_optional(
        self,
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
        *,
        optional: bool,
    ) -> dict[str, Any]:
        generic = deepcopy(schema_generic_device)
        assert generic["attributes"][1]["name"] == "asset_tag"
        generic["attributes"][1]["optional"] = optional
        return {
            "version": "1.0",
            "generics": [generic],
            "nodes": [deepcopy(schema_router), deepcopy(schema_switch)],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_step_01: dict[str, Any],
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        router = await Node.init(schema=ROUTER_KIND, db=db)
        await router.new(db=db, name="router1", asset_tag="RTR-001")
        await router.save(db=db)

        switch = await Node.init(schema=SWITCH_KIND, db=db)
        await switch.new(db=db, name="switch1", asset_tag="SW-001")
        await switch.save(db=db)

        return {"router1": router.id, "switch1": switch.id}

    async def test_step01_baseline(self, initial_dataset: dict[str, str]) -> None:
        """The generic and both child nodes start with a mandatory asset_tag."""
        schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        for kind in (GENERIC_KIND, ROUTER_KIND, SWITCH_KIND):
            assert schema_branch.get(name=kind, duplicate=False).get_attribute("asset_tag").optional is False, kind

    async def test_step02_mandatory_to_optional(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> None:
        """Relaxing the generic attribute to optional propagates to every inheriting child node."""
        updated = self._schema_with_optional(schema_generic_device, schema_router, schema_switch, optional=True)
        response = await client.schema.load(schemas=[updated])
        assert not response.errors

        schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        for kind in (GENERIC_KIND, ROUTER_KIND, SWITCH_KIND):
            assert schema_branch.get(name=kind, duplicate=False).get_attribute("asset_tag").optional is True, kind

        # A child instance can now be created without the previously mandatory field.
        router2 = await Node.init(schema=ROUTER_KIND, db=db)
        await router2.new(db=db, name="router2")
        await router2.save(db=db)
        initial_dataset["router2"] = router2.id

    async def test_step03_optional_to_mandatory_blocked_with_nulls(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> None:
        """Tightening back to mandatory is rejected while router2 still has a null asset_tag."""
        reverted = self._schema_with_optional(schema_generic_device, schema_router, schema_switch, optional=False)
        response = await client.schema.load(schemas=[reverted])
        assert response.errors, "Expected the optional->mandatory change to be rejected"

        # The error must identify the offending object: the concrete child kind, the failing
        # constraint, and the specific instance (router2, the one created without an asset_tag).
        message = response.errors["errors"][0]["message"]
        assert "'optional' constraint violation" in message, message
        assert ROUTER_KIND in message, message
        assert initial_dataset["router2"] in message, message

    async def test_step04_optional_to_mandatory_succeeds_when_populated(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> None:
        """Once every instance has a value, the optional->mandatory change is accepted."""
        router2 = await registry.manager.get_one(db=db, id=initial_dataset["router2"])
        assert router2 is not None
        router2.asset_tag.value = "RTR-002"  # type: ignore[attr-defined]
        await router2.save(db=db)

        reverted = self._schema_with_optional(schema_generic_device, schema_router, schema_switch, optional=False)
        response = await client.schema.load(schemas=[reverted])
        assert not response.errors

        schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        for kind in (GENERIC_KIND, ROUTER_KIND, SWITCH_KIND):
            assert schema_branch.get(name=kind, duplicate=False).get_attribute("asset_tag").optional is False, kind

    async def test_step05_child_can_override_to_mandatory(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_generic_device: dict[str, Any],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> None:
        """The generic is optional, but a child overrides the attribute back to mandatory."""
        generic = deepcopy(schema_generic_device)
        generic["attributes"][1]["optional"] = True

        switch_override = deepcopy(schema_switch)
        switch_override["attributes"] = [{"name": "asset_tag", "kind": "Text", "optional": False}]

        updated = {
            "version": "1.0",
            "generics": [generic],
            "nodes": [deepcopy(schema_router), switch_override],
        }
        response = await client.schema.load(schemas=[updated])
        assert not response.errors

        schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        assert schema_branch.get(name=GENERIC_KIND, duplicate=False).get_attribute("asset_tag").optional is True
        # Router inherits the generic's optional setting...
        assert schema_branch.get(name=ROUTER_KIND, duplicate=False).get_attribute("asset_tag").optional is True
        # ...while Switch keeps its local mandatory override.
        assert schema_branch.get(name=SWITCH_KIND, duplicate=False).get_attribute("asset_tag").optional is False

        # The inheriting child can be created without the field.
        router3 = await Node.init(schema=ROUTER_KIND, db=db)
        await router3.new(db=db, name="router3")
        await router3.save(db=db)

    async def test_step06_optional_blocked_when_referenced_in_hfid(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_router: dict[str, Any],
        schema_switch: dict[str, Any],
    ) -> None:
        """An optional attribute (no default) referenced in a human_friendly_id is rejected."""
        generic = {
            "name": "Device",
            "namespace": "Testing",
            "human_friendly_id": ["name__value", "asset_tag__value"],
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "asset_tag", "kind": "Text", "optional": True},
            ],
        }
        switch_override = deepcopy(schema_switch)
        switch_override["attributes"] = [{"name": "asset_tag", "kind": "Text", "optional": False}]
        updated = {
            "version": "1.0",
            "generics": [generic],
            "nodes": [deepcopy(schema_router), switch_override],
        }
        response = await client.schema.load(schemas=[updated])
        assert response.errors, "Expected the hfid/uniqueness guard to reject the optional attribute"
        message = response.errors["errors"][0]["message"]
        assert "human_friendly_id" in message, message
        assert "asset_tag" in message, message

    async def test_step07_optional_in_hfid_allowed_with_default(self, client: InfrahubClient) -> None:
        """An optional attribute in a human_friendly_id is allowed when it has a default_value."""
        tagged = {
            "name": "Tagged",
            "namespace": "Testing",
            "human_friendly_id": ["name__value", "status__value"],
            "attributes": [
                {"name": "name", "kind": "Text"},
                # status is optional (default_value implies optional) but always populated, so it is
                # safe to use in the human_friendly_id.
                {"name": "status", "kind": "Text", "default_value": "active"},
            ],
        }
        response = await client.schema.load(schemas=[{"version": "1.0", "generics": [tagged]}])
        assert not response.errors

        schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        status_attr = schema_branch.get(name=TAGGED_KIND, duplicate=False).get_attribute("status")
        assert status_attr.optional is True
        assert status_attr.default_value == "active"
