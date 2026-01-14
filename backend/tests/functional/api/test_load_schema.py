from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.schema import GenericSchemaAPI as SDKGenericSchema

from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.query.node import MetadataOptions
from infrahub.core.registry import registry
from infrahub.core.schema import core_models
from infrahub.core.schema.basenode_schema import OPTIONAL_TEXT_FIELDS
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.branch import BranchData

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator
    from tests.conftest import TestHelper


class TestLoadSchemaAPI(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        pass

    async def test_schema_load_endpoint_idempotent_simple(
        self, initial_dataset: str, client: InfrahubClient, helper: TestHelper, db: InfrahubDatabase
    ) -> None:
        creation = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert creation.schema_updated
        test_device = await client.schema.get(kind="TestDevice")
        attributes = {attrib.name: attrib.order_weight for attrib in test_device.attributes}
        relationships = {attrib.name: attrib.order_weight for attrib in test_device.relationships}
        assert attributes["name"] == 1000
        assert attributes["description"] == 900
        assert attributes["type"] == 3000
        assert relationships["interfaces"] == 450
        assert relationships["tags"] == 7000

        first_relationship_count = await count_relationships(db=db)
        update = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not update.schema_updated
        updated_relationship_count = await count_relationships(db=db)

        assert first_relationship_count == updated_relationship_count

    async def test_schema_migration_updates_node_metadata(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Test that schema migrations update node metadata (updated_at/by) correctly."""
        # Load initial schema
        await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])

        # Create a TestDevice node
        device = await client.create(
            kind="TestDevice",
            name="metadata-test-device",
            type="router",
            role="router",
            status="active",
        )
        await device.save()
        device_id = device.id

        # Record time before schema change
        time_before_migration = Timestamp()

        # Modify schema to add a new attribute to TestDevice
        updated_schema = helper.schema_file("infra_simple_01.json")
        for node in updated_schema["nodes"]:
            if node["name"] == "Device" and node["namespace"] == "Test":
                node["attributes"].append({"name": "location", "kind": "Text", "optional": True})
                break

        # Load updated schema - this should trigger a migration
        update_result = await client.schema.load(schemas=[updated_schema])
        assert update_result.schema_updated

        # Query the node with metadata
        nodes = await NodeManager.get_many(
            db=db,
            ids=[device_id],
            branch=default_branch,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
            ),
        )
        node = nodes[device_id]

        # Verify node metadata was updated by the migration
        assert node._get_created_at() < time_before_migration
        assert node._get_created_by() == admin_account.id
        assert node._get_updated_at() > time_before_migration
        assert node._get_updated_by() == admin_account.id

        # Verify the new attribute exists and has proper metadata
        assert node.location._get_created_at() > time_before_migration
        assert node.location._get_created_by() == admin_account.id
        assert node.location._get_updated_at() == node.location._get_created_at()
        assert node.location._get_updated_by() == admin_account.id

    async def test_schema_load_with_absent_schema(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])

        # get the organization schema
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        organization_schema = schema_branch.get_node(name="TestingOrganization", duplicate=False)
        tags_relationship = organization_schema.get_relationship(name="tags")
        description_attribute = organization_schema.get_attribute(name="description")

        # set the organization and relationships to absent
        updated_schema = helper.schema_file("infra_simple_01.json")
        for node in updated_schema["nodes"]:
            if node["name"] == "Organization" and node["namespace"] == "Testing":
                node["state"] = "absent"
                for rel in node["relationships"]:
                    rel["state"] = "absent"
                for attr in node["attributes"]:
                    if attr["name"] == "description":
                        attr["state"] = "absent"

        update = await client.schema.load(schemas=[updated_schema])
        assert update.schema_updated

        # try to get the organization schema
        org_schema_node = await NodeManager.get_one(db=db, id=organization_schema.get_id())
        assert org_schema_node is None
        # try to get the tags relationship
        tags_relationship_node = await NodeManager.get_one(db=db, id=tags_relationship.get_id())
        assert tags_relationship_node is None
        # try to get the description attribute
        description_attribute_node = await NodeManager.get_one(db=db, id=description_attribute.get_id())
        assert description_attribute_node is None

    async def test_schema_load_endpoint_idempotent_with_generics(
        self, initial_dataset: str, client: InfrahubClient, helper: TestHelper, db: InfrahubDatabase
    ) -> None:
        creation = await client.schema.load(schemas=[helper.schema_file("infra_w_generics_01.json")])
        assert creation.schema_updated
        assert creation.schema_updated
        first_relationship_count = await count_relationships(db=db)
        update = await client.schema.load(schemas=[helper.schema_file("infra_w_generics_01.json")])
        assert not update.schema_updated
        updated_relationship_count = await count_relationships(db=db)

        assert first_relationship_count == updated_relationship_count

        all_schemas = await client.schema.all(refresh=True)
        generic_schemas = [schema for schema in all_schemas.values() if isinstance(schema, SDKGenericSchema)]

        assert len(generic_schemas) == len(core_models["generics"]) + 1

    async def test_schema_load_existing_node_different_kind(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db, at=Timestamp())
        creation = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not creation.errors

        modified_schema = helper.schema_file("infra_simple_01.json")
        modified_schema["nodes"].pop(0)
        modified_schema["generics"] = [
            {
                "name": "Device",
                "namespace": "Infra",
                "label": "A generic with the same kind as an existing node in the schema",
            }
        ]

        modification = await client.schema.load(schemas=[modified_schema])
        assert modification.errors
        assert modification.errors["errors"]
        assert len(modification.errors["errors"]) == 1
        error = modification.errors["errors"][0]
        assert (
            error["message"]
            == "InfraDevice already exist in the schema as a Node. Either rename it or delete the existing one."
        )
        assert error["extensions"]["code"] == 422

    async def test_schema_load_endpoint_valid_with_extensions(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db, at=Timestamp())
        simple = await client.schema.load(schemas=[helper.schema_file("infra_simple_01.json")])
        assert not simple.errors
        org_schema = registry.schema.get(name="TestingOrganization", branch=default_branch.name)
        initial_nbr_relationships = len(org_schema.relationships)

        extended_schema = await client.schema.load(schemas=[helper.schema_file("infra_w_extensions_01.json")])
        assert not extended_schema.errors
        assert extended_schema.schema_updated

        org_schema = registry.schema.get(name="TestingOrganization", branch=default_branch.name)
        assert len(org_schema.relationships) == initial_nbr_relationships + 1

    @pytest.fixture(scope="class")
    async def extension_branch(self, client: InfrahubClient) -> BranchData:
        return await client.branch.create(branch_name="extension_branch")

    @pytest.fixture(scope="class")
    async def load_extension_schema_00(self, client: InfrahubClient) -> None:
        start_schema_dict = {
            "version": "1.0",
            "generics": [
                {
                    "name": "Generic",
                    "namespace": "Thing",
                    "attributes": [{"kind": "Text", "name": "name"}],
                    "relationships": [
                        {
                            "cardinality": "many",
                            "kind": "Attribute",
                            "name": "interfaces",
                            "optional": True,
                            "peer": "TestInterface",
                        }
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "Node",
                    "namespace": "Thing",
                    "inherit_from": ["ThingGeneric"],
                    "attributes": [
                        {"kind": "Text", "name": "description", "optional": True},
                    ],
                },
            ],
        }
        simple = await client.schema.load(schemas=[start_schema_dict])
        assert not simple.errors

    @pytest.fixture(scope="class")
    async def load_extension_schema_01(self, client: InfrahubClient, extension_branch: BranchData) -> None:
        extension_schema_dict = {
            "version": "1.0",
            "extensions": {
                "nodes": [
                    {
                        "kind": "ThingNode",
                        "attributes": [
                            {"kind": "Text", "name": "something", "optional": True},
                        ],
                        "relationships": [
                            {
                                "name": "devices",
                                "peer": "InfraDevice",
                                "kind": "Generic",
                                "cardinality": "many",
                                "optional": True,
                            }
                        ],
                    }
                ]
            },
        }
        extended_schema = await client.schema.load(branch=extension_branch.name, schemas=[extension_schema_dict])
        assert not extended_schema.errors
        assert extended_schema.schema_updated

    @pytest.fixture(scope="class")
    async def load_extension_schema_02(self, client: InfrahubClient, extension_branch: BranchData) -> None:
        extension_schema_dict = {
            "version": "1.0",
            "extensions": {
                "nodes": [
                    {
                        "kind": "ThingNode",
                        "attributes": [
                            {"kind": "Text", "name": "something_new", "optional": True},
                        ],
                        "relationships": [
                            {
                                "name": "devices_new",
                                "peer": "InfraDevice",
                                "identifier": "devices_new_thing",
                                "kind": "Generic",
                                "cardinality": "many",
                                "optional": True,
                            }
                        ],
                    }
                ]
            },
        }
        extended_schema = await client.schema.load(branch=extension_branch.name, schemas=[extension_schema_dict])
        assert not extended_schema.errors
        assert extended_schema.schema_updated

    @pytest.fixture(scope="class")
    async def load_extension_schema_03(
        self, db: InfrahubDatabase, client: InfrahubClient, extension_branch: BranchData
    ) -> None:
        generic_schema = registry.schema.get(name="ThingGeneric")
        retrieved_generic_schema = await NodeManager.get_one(db=db, id=generic_schema.get_id())
        schema_attrs = await retrieved_generic_schema.attributes.get(db=db)
        name_attr: Node | None = None
        for a in schema_attrs:
            schema_attr_peer = await a.get_peer(db)
            if schema_attr_peer.name.value == "name":
                name_attr = schema_attr_peer
                break
        if not name_attr:
            raise ValueError("Cannot find 'name' attribute on ThingGeneric")

        schema_dict = {
            "version": "1.0",
            "generics": [
                {
                    "name": "Generic",
                    "namespace": "Thing",
                    "attributes": [{"id": name_attr.id, "kind": "Text", "name": "hot_new_name"}],
                    "human_friendly_id": [],
                    "relationships": [
                        {
                            "cardinality": "many",
                            "kind": "Attribute",
                            "name": "interfaces",
                            "optional": True,
                            "peer": "TestInterface",
                        }
                    ],
                }
            ],
        }
        simple = await client.schema.load(schemas=[schema_dict], branch=extension_branch.name)
        assert not simple.errors

    async def test_schema_load_endpoint_valid_generic_with_extensions(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_extension_schema_00,
        load_extension_schema_01,
        extension_branch: BranchData,
    ) -> None:
        node_schema = registry.schema.get(name="ThingNode", branch=default_branch.name)
        initial_nbr_relationships = len(node_schema.relationships)
        initial_nbr_attributes = len(node_schema.attributes)
        branch_name = extension_branch.name

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_name)
        node_schema = schema_branch.get_node(name="ThingNode", duplicate=False)
        assert len(node_schema.relationships) == initial_nbr_relationships + 1
        assert len(node_schema.attributes) == initial_nbr_attributes + 1

        # check that the node schema on the database has the expected relationships and attributes on the branch
        assert set(node_schema.relationship_names) == {
            "devices",
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.local_relationship_names) == {
            "devices",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.attribute_names) == {"name", "description", "something"}
        assert set(node_schema.local_attribute_names) == {"description", "something"}

        # check that the generic schema on the database has the expected relationships and attributes on the branch
        generic_schema = schema_branch.get_generic(name="ThingGeneric", duplicate=False)
        assert set(generic_schema.relationship_names) == {
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert generic_schema.attribute_names == ["name"]

    async def test_schema_load_endpoint_valid_generic_with_extension_updates(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_extension_schema_02,
        extension_branch: BranchData,
    ) -> None:
        node_schema = registry.schema.get(name="ThingNode", branch=default_branch.name)
        initial_nbr_relationships = len(node_schema.relationships)
        initial_nbr_attributes = len(node_schema.attributes)
        branch_name = extension_branch.name

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_name)
        node_schema = schema_branch.get_node(name="ThingNode", duplicate=False)
        assert len(node_schema.relationships) == initial_nbr_relationships + 2
        assert len(node_schema.attributes) == initial_nbr_attributes + 2

        # check that the node schema on the database has the expected relationships and attributes on the branch
        assert set(node_schema.relationship_names) == {
            "devices",
            "devices_new",
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.local_relationship_names) == {
            "devices",
            "devices_new",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.attribute_names) == {"name", "description", "something", "something_new"}
        assert set(node_schema.local_attribute_names) == {"description", "something", "something_new"}

        # check that the generic schema on the database has the expected relationships and attributes on the branch
        generic_schema = schema_branch.get_generic(name="ThingGeneric", duplicate=False)
        assert set(generic_schema.relationship_names) == {
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert generic_schema.attribute_names == ["name"]

    async def test_schema_load_endpoint_valid_generic_with_generic_name_updates(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_extension_schema_03,
        extension_branch: BranchData,
    ) -> None:
        node_schema = registry.schema.get(name="ThingNode", branch=default_branch.name)
        initial_nbr_relationships = len(node_schema.relationships)
        initial_nbr_attributes = len(node_schema.attributes)
        branch_name = extension_branch.name

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_name)
        node_schema = schema_branch.get_node(name="ThingNode", duplicate=False)
        assert len(node_schema.relationships) == initial_nbr_relationships + 2
        assert len(node_schema.attributes) == initial_nbr_attributes + 2

        # check that the node schema on the database has the expected relationships and attributes on the branch
        assert set(node_schema.relationship_names) == {
            "devices",
            "devices_new",
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.local_relationship_names) == {
            "devices",
            "devices_new",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert set(node_schema.attribute_names) == {"hot_new_name", "description", "something", "something_new"}
        assert set(node_schema.local_attribute_names) == {"description", "something", "something_new"}

        # check that the generic schema on the database has the expected relationships and attributes on the branch
        generic_schema = schema_branch.get_generic(name="ThingGeneric", duplicate=False)
        assert set(generic_schema.relationship_names) == {
            "interfaces",
            "profiles",
            "member_of_groups",
            "subscriber_of_groups",
        }
        assert generic_schema.attribute_names == ["hot_new_name"]

    async def test_remove_optional_text_field_value(
        self,
        initial_dataset: str,
        client: InfrahubClient,
        helper: TestHelper,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        schema_dict = {
            "version": "1.0",
            "generics": [
                {
                    "name": "Location",
                    "namespace": "Test",
                    "hierarchical": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "description", "kind": "Text", "optional": True},
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "Continent",
                    "namespace": "Test",
                    "inherit_from": ["TestLocation"],
                },
                {
                    "name": "Country",
                    "namespace": "Test",
                    "inherit_from": ["TestLocation"],
                    "default_filter": "name__value",
                    "description": "test description",
                    "label": "MyPersonLabel",
                    "menu_placement": "menu value",
                    "documentation": "http://localhost",
                    "parent": "TestContinent",
                    "children": "TestContinent",
                },
            ],
        }

        country_schema_node = schema_dict["nodes"][1]
        assert country_schema_node["name"] == "Country"  # type: ignore
        for field_name in OPTIONAL_TEXT_FIELDS:
            assert field_name in country_schema_node

        creation = await client.schema.load(schemas=[schema_dict])
        assert creation.schema_updated
        assert not creation.errors

        schema = await client.schema.get(kind="TestCountry", refresh=True)
        assert schema.default_filter == "name__value"
        assert schema.description == "test description"
        assert schema.label == "MyPersonLabel"
        assert schema.menu_placement == "menu value"
        assert schema.documentation == "http://localhost"
        assert schema.parent == "TestContinent"
        assert schema.children == "TestContinent"

        country_schema_node["default_filter"] = ""  # type: ignore
        country_schema_node["description"] = ""  # type: ignore
        country_schema_node["label"] = ""  # type: ignore
        country_schema_node["menu_placement"] = ""  # type: ignore
        country_schema_node["documentation"] = ""  # type: ignore
        country_schema_node["parent"] = ""  # type: ignore
        country_schema_node["children"] = ""  # type: ignore

        creation = await client.schema.load(schemas=[schema_dict])
        assert creation.schema_updated

        schema = await client.schema.get(kind="TestCountry", refresh=True)
        assert schema.default_filter is None
        assert schema.description is None
        assert schema.label == "Country"
        assert schema.menu_placement is None
        assert schema.documentation is None
        assert schema.parent == "TestLocation"
        assert schema.children == "TestLocation"
