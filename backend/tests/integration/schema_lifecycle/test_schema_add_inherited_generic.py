import copy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships
from tests.helpers.db_validation import validate_no_duplicate_attributes, verify_graph

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

SERVER_KIND = "TestingServer"
ASSET_KIND = "TestingAsset"
SWITCH_KIND = "TestingSwitch"


class TestSchemaAddInheritedGeneric(TestSchemaLifecycleBase):
    """A kind that newly inherits a generic must gain working attribute rows on pre-existing nodes."""

    @pytest.fixture(scope="class")
    def schema_server_base(self) -> dict[str, Any]:
        return {
            "name": "Server",
            "namespace": "Testing",
            "label": "Server",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_switch_base(self) -> dict[str, Any]:
        return {
            "name": "Switch",
            "namespace": "Testing",
            "label": "Switch",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_asset_generic(self) -> dict[str, Any]:
        return {
            "name": "Asset",
            "namespace": "Testing",
            "label": "Asset",
            "attributes": [
                {
                    "name": "status",
                    "kind": "Dropdown",
                    "choices": [{"name": "active"}, {"name": "planned"}],
                    "default_value": "active",
                    "optional": True,
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_server_02_inherit_asset(self, schema_server_base: dict[str, Any]) -> dict[str, Any]:
        """The server kind starts inheriting the asset generic."""
        server = copy.deepcopy(schema_server_base)
        server["inherit_from"] = [ASSET_KIND]
        return server

    @pytest.fixture(scope="class")
    def schema_asset_04_owner(self, schema_asset_generic: dict[str, Any]) -> dict[str, Any]:
        """The asset generic gains a new owner attribute."""
        generic = copy.deepcopy(schema_asset_generic)
        generic["attributes"].append({"name": "owner", "kind": "Text", "default_value": "unassigned", "optional": True})
        return generic

    @pytest.fixture(scope="class")
    def schema_switch_04_inherit_asset_and_ip(self, schema_switch_base: dict[str, Any]) -> dict[str, Any]:
        """The switch kind starts inheriting the asset generic and gains its own new attribute."""
        switch = copy.deepcopy(schema_switch_base)
        switch["inherit_from"] = [ASSET_KIND]
        switch["attributes"].append({"name": "management_ip", "kind": "Text", "optional": True})
        return switch

    @pytest.fixture(scope="class")
    def schema_step01(self, schema_server_base: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_server_base]}

    @pytest.fixture(scope="class")
    def schema_step02(
        self, schema_server_02_inherit_asset: dict[str, Any], schema_asset_generic: dict[str, Any]
    ) -> dict[str, Any]:
        return {"version": "1.0", "generics": [schema_asset_generic], "nodes": [schema_server_02_inherit_asset]}

    @pytest.fixture(scope="class")
    def schema_step03(
        self,
        schema_server_02_inherit_asset: dict[str, Any],
        schema_asset_generic: dict[str, Any],
        schema_switch_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_asset_generic],
            "nodes": [schema_server_02_inherit_asset, schema_switch_base],
        }

    @pytest.fixture(scope="class")
    def schema_step04(
        self,
        schema_server_02_inherit_asset: dict[str, Any],
        schema_asset_04_owner: dict[str, Any],
        schema_switch_04_inherit_asset_and_ip: dict[str, Any],
    ) -> dict[str, Any]:
        """One schema load where an existing kind gains an existing generic and both gain a new attribute."""
        return {
            "version": "1.0",
            "generics": [schema_asset_04_owner],
            "nodes": [schema_server_02_inherit_asset, schema_switch_04_inherit_asset_and_ip],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step01)

        server1 = await Node.init(schema=SERVER_KIND, db=db)
        await server1.new(db=db, name="server-1")
        await server1.save(db=db)

        server2 = await Node.init(schema=SERVER_KIND, db=db)
        await server2.new(db=db, name="server-2")
        await server2.save(db=db)

        return {"server1": server1.id, "server2": server2.id}

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        servers = await NodeManager.query(db=db, schema=SERVER_KIND)
        assert len(servers) == 2

    async def test_step02_load_inherited_generic(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step02: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_step02])
        assert not response.errors

    async def test_step02_read_returns_real_attribute(
        self, db: InfrahubDatabase, initial_dataset: dict[str, str]
    ) -> None:
        servers = await NodeManager.query(db=db, schema=SERVER_KIND, filters={"name__value": "server-1"})
        assert len(servers) == 1
        status_attr = servers[0].get_attribute(name="status")
        assert status_attr.id is not None
        assert status_attr.value == "active"
        assert status_attr.is_default is True

    async def test_step02_update_persists(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        servers = await NodeManager.query(db=db, schema=SERVER_KIND, filters={"name__value": "server-1"})
        assert len(servers) == 1
        server = servers[0]
        server.get_attribute(name="status").value = "planned"
        await server.save(db=db)

        refetched = await NodeManager.query(db=db, schema=SERVER_KIND, filters={"name__value": "server-1"})
        assert len(refetched) == 1
        status_attr = refetched[0].get_attribute(name="status")
        assert status_attr.value == "planned"
        assert status_attr.is_default is False

    async def test_step02_filter_matches(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        # server-2 was never explicitly updated and must match on the inherited default
        matches = await NodeManager.query(db=db, schema=SERVER_KIND, filters={"status__value": "active"})
        assert [node.id for node in matches] == [initial_dataset["server2"]]

    async def test_step03_add_switch_schema(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step03: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_step03])
        assert not response.errors

        switch1 = await Node.init(schema=SWITCH_KIND, db=db)
        await switch1.new(db=db, name="switch-1")
        await switch1.save(db=db)

        switch2 = await Node.init(schema=SWITCH_KIND, db=db)
        await switch2.new(db=db, name="switch-2")
        await switch2.save(db=db)

    async def test_step04_load_compound_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step04: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_step04])
        assert not response.errors

    async def test_step04_switch_gains_all_attributes(self, db: InfrahubDatabase) -> None:
        """A switch pre-dating the inheritance gains the generic's original and new attributes plus the kind's own new attribute in one load."""
        switches = await NodeManager.query(db=db, schema=SWITCH_KIND, filters={"name__value": "switch-1"})
        assert len(switches) == 1
        switch = switches[0]
        for attr_name, expected_value in [("status", "active"), ("owner", "unassigned"), ("management_ip", None)]:
            attr = switch.get_attribute(name=attr_name)
            assert attr.id is not None
            assert attr.value == expected_value
            assert attr.is_default is True

        switch.get_attribute(name="status").value = "planned"
        switch.get_attribute(name="owner").value = "dc-team"
        switch.get_attribute(name="management_ip").value = "192.0.2.10"
        await switch.save(db=db)

        refetched = await NodeManager.get_one(db=db, id=switch.id)
        for attr_name, expected_value in [("status", "planned"), ("owner", "dc-team"), ("management_ip", "192.0.2.10")]:
            attr = refetched.get_attribute(name=attr_name)
            assert attr.value == expected_value
            assert attr.is_default is False

    async def test_step04_server_gains_generic_attribute(
        self, db: InfrahubDatabase, initial_dataset: dict[str, str]
    ) -> None:
        """Servers that already inherited the generic gain only the generic's new attribute and keep previously written values."""
        servers = await NodeManager.query(db=db, schema=SERVER_KIND)
        assert len(servers) == 2
        servers_by_id = {server.id: server for server in servers}
        assert set(servers_by_id) == {initial_dataset["server1"], initial_dataset["server2"]}
        for server in servers_by_id.values():
            owner_attr = server.get_attribute(name="owner")
            assert owner_attr.id is not None
            assert owner_attr.value == "unassigned"
            assert owner_attr.is_default is True
        server1 = servers_by_id[initial_dataset["server1"]]
        status_attr = server1.get_attribute(name="status")
        assert status_attr.value == "planned"
        assert status_attr.is_default is False

        server1.get_attribute(name="owner").value = "infra-team"
        await server1.save(db=db)
        refetched = await NodeManager.get_one(db=db, id=server1.id)
        assert refetched.get_attribute(name="owner").value == "infra-team"
        assert refetched.get_attribute(name="owner").is_default is False

    async def test_step04_no_duplicate_attribute_rows(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        assert await validate_no_duplicate_attributes(db=db, branch=default_branch) == []

    async def test_step04_update_and_filter(self, db: InfrahubDatabase) -> None:
        switches = await NodeManager.query(db=db, schema=SWITCH_KIND, filters={"name__value": "switch-2"})
        assert len(switches) == 1
        switch = switches[0]
        switch.get_attribute(name="owner").value = "netops"
        await switch.save(db=db)

        matches = await NodeManager.query(db=db, schema=SWITCH_KIND, filters={"owner__value": "netops"})
        assert [node.id for node in matches] == [switch.id]

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_graph(db=db)
