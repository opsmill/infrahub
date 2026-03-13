"""Verify that removing a Number attribute (or changing its kind) also removes
the corresponding _from_resource_pool relationship from the template schema.

Flow:
  step01 - load schema with Number attribute, verify template has pool rel
  step02 - remove the Number attribute, verify template loses pool rel
  step03 - re-add the Number attribute, verify template has pool rel again
  step04 - change the Number attribute to Text, verify template loses pool rel
"""

from copy import deepcopy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

DEVICE_KIND = "TestingDevice"
TEMPLATE_DEVICE_KIND = "TemplateTestingDevice"
POOL_REL_NAME = f"vlan_id{RESOURCE_POOL_REL_SUFFIX}"


class TestAttrRemovePoolRelCleanup(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_device_base(self) -> dict[str, Any]:
        return {
            "name": "Device",
            "namespace": "Testing",
            "generate_template": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "vlan_id", "kind": "Number", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(self, schema_device_base: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_device_base]}

    @pytest.fixture(scope="class")
    def schema_device_no_vlan(self, schema_device_base: dict[str, Any]) -> dict[str, Any]:
        schema = deepcopy(schema_device_base)
        for attr in schema["attributes"]:
            if attr["name"] == "vlan_id":
                attr["state"] = "absent"
        return schema

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_device_no_vlan: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_device_no_vlan]}

    @pytest.fixture(scope="class")
    def schema_step_03(self, schema_device_base: dict[str, Any]) -> dict[str, Any]:
        """Re-add vlan_id by loading the original schema again."""
        return {"version": "1.0", "nodes": [deepcopy(schema_device_base)]}

    @pytest.fixture(scope="class")
    def schema_device_vlan_as_text(self, schema_device_base: dict[str, Any]) -> dict[str, Any]:
        schema = deepcopy(schema_device_base)
        for attr in schema["attributes"]:
            if attr["name"] == "vlan_id":
                attr["kind"] = "Text"
        return schema

    @pytest.fixture(scope="class")
    def schema_step_04(self, schema_device_vlan_as_text: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_device_vlan_as_text]}

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_step_01: dict[str, Any],
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        device = await Node.init(schema=DEVICE_KIND, db=db)
        await device.new(db=db, name="spine-01", vlan_id=100, description="Spine switch")
        await device.save(db=db)

        # Template without pool relationship
        template_no_pool = await Node.init(schema=TEMPLATE_DEVICE_KIND, db=db)
        await template_no_pool.new(db=db, template_name="spine-template", vlan_id=200)
        await template_no_pool.save(db=db)

        # Create a NumberPool for vlan_id
        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="vlan-pool",
            node=DEVICE_KIND,
            node_attribute="vlan_id",
            start_range=1,
            end_range=4094,
        )
        await pool.save(db=db)

        # Template with pool relationship set
        template_with_pool = await Node.init(schema=TEMPLATE_DEVICE_KIND, db=db)
        await template_with_pool.new(
            db=db,
            template_name="spine-template-pooled",
            vlan_id_from_resource_pool=pool,
        )
        await template_with_pool.save(db=db)

        return {
            "device": device.id,
            "template_no_pool": template_no_pool.id,
            "template_with_pool": template_with_pool.id,
            "pool": pool.id,
        }

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """Template schema has vlan_id_from_resource_pool relationship."""
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_DEVICE_KIND)
        assert POOL_REL_NAME in template_schema.relationship_names
        assert "vlan_id" in template_schema.attribute_names

        # Template without pool is accessible, pool rel has no peer
        tpl_no_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_no_pool"])
        assert tpl_no_pool is not None
        pool_peer = await tpl_no_pool.vlan_id_from_resource_pool.get_peer(db=db)  # type: ignore[attr-defined]
        assert pool_peer is None

        # Template with pool is accessible, pool rel points to the pool
        tpl_with_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_with_pool"])
        assert tpl_with_pool is not None
        pool_peer = await tpl_with_pool.vlan_id_from_resource_pool.get_peer(db=db)  # type: ignore[attr-defined]
        assert pool_peer is not None
        assert pool_peer.id == initial_dataset["pool"]

    async def test_step02_remove_number_attr(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        """Removing vlan_id removes both the attribute and pool rel from the template schema."""
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        # Node schema no longer has vlan_id
        device_schema = registry.schema.get_node_schema(name=DEVICE_KIND)
        assert "vlan_id" not in device_schema.attribute_names

        # Template schema no longer has vlan_id attribute or pool relationship
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_DEVICE_KIND)
        assert "vlan_id" not in template_schema.attribute_names
        assert POOL_REL_NAME not in template_schema.relationship_names

        # Template without pool: still accessible, pool rel no longer exposed
        tpl_no_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_no_pool"])
        assert tpl_no_pool is not None
        with pytest.raises(ValueError, match="vlan_id"):
            tpl_no_pool.get_attribute("vlan_id")
        with pytest.raises(ValueError, match=POOL_REL_NAME):
            tpl_no_pool.get_relationship(POOL_REL_NAME)

        # Template with pool: still accessible, pool rel no longer exposed
        tpl_with_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_with_pool"])
        assert tpl_with_pool is not None
        with pytest.raises(ValueError, match="vlan_id"):
            tpl_with_pool.get_attribute("vlan_id")
        with pytest.raises(ValueError, match=POOL_REL_NAME):
            tpl_with_pool.get_relationship(POOL_REL_NAME)

    async def test_step03_readd_number_attr(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_03: dict[str, Any],
    ) -> None:
        """Re-adding vlan_id restores both the attribute and pool rel on the template schema."""
        response = await client.schema.load(schemas=[schema_step_03])
        assert not response.errors

        # Node schema has vlan_id again
        device_schema = registry.schema.get_node_schema(name=DEVICE_KIND)
        assert "vlan_id" in device_schema.attribute_names

        # Template schema has vlan_id attribute and pool relationship again
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_DEVICE_KIND)
        assert "vlan_id" in template_schema.attribute_names
        assert POOL_REL_NAME in template_schema.relationship_names

    async def test_step04_change_number_to_text(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_04: dict[str, Any],
    ) -> None:
        """Changing vlan_id from Number to Text removes the pool rel but keeps the attribute."""
        response = await client.schema.load(schemas=[schema_step_04])
        assert not response.errors

        # Node schema has vlan_id with Text kind
        device_schema = registry.schema.get_node_schema(name=DEVICE_KIND)
        assert "vlan_id" in device_schema.attribute_names
        assert device_schema.get_attribute("vlan_id").kind == "Text"

        # Template schema has vlan_id attribute but NOT the pool relationship
        template_schema = registry.schema.get_template_schema(name=TEMPLATE_DEVICE_KIND)
        assert "vlan_id" in template_schema.attribute_names
        assert template_schema.get_attribute("vlan_id").kind == "Text"
        assert POOL_REL_NAME not in template_schema.relationship_names

        # Template without pool: accessible, pool rel not exposed
        tpl_no_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_no_pool"])
        assert tpl_no_pool is not None
        assert tpl_no_pool.get_attribute("vlan_id").value is None
        with pytest.raises(ValueError, match=POOL_REL_NAME):
            tpl_no_pool.get_relationship(POOL_REL_NAME)

        # Template with pool: accessible, pool rel not exposed
        tpl_with_pool = await registry.manager.get_one(db=db, id=initial_dataset["template_with_pool"])
        assert tpl_with_pool is not None
        assert tpl_with_pool.get_attribute("vlan_id").value is None
        with pytest.raises(ValueError, match=POOL_REL_NAME):
            tpl_with_pool.get_relationship(POOL_REL_NAME)
