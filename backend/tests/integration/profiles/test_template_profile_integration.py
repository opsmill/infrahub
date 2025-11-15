"""Integration tests for template profile support."""

import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipCardinality, RelationshipSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp


class TestTemplateProfileIntegration(TestInfrahubApp):
    """Test template profile support through GraphQL and Python SDK."""

    @pytest.fixture(scope="class")
    def device_schema_base(self) -> NodeSchema:
        """Create a device schema with template and profile support."""
        return NodeSchema(
            name="Device",
            namespace="Testing",
            generate_template=True,
            generate_profile=True,
            label="Device",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="manufacturer", kind="Text", optional=True),
                AttributeSchema(name="model", kind="Text", optional=True),
                AttributeSchema(name="height", kind="Number", optional=True),
                AttributeSchema(name="weight", kind="Number", optional=True),
                AttributeSchema(name="airflow", kind="Text", optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    async def schema_root_01(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_schema_base: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        """Load the device schema with template and profile support."""
        schema_root = SchemaRoot(version="1.0", nodes=[device_schema_base])
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def device_profile(self, db: InfrahubDatabase, schema_root_01) -> Node:
        """Create a device profile."""
        profile_schema = registry.schema.get_node_schema(name="ProfileTestingDevice", duplicate=False)
        device_profile = await Node.init(db=db, schema=profile_schema)
        await device_profile.new(
            db=db,
            profile_name="high_density_profile",
            profile_priority=100,
            airflow="Front to rear",
            height=1,
        )
        await device_profile.save(db=db)
        return device_profile

    @pytest.fixture(scope="class")
    async def device_template(self, db: InfrahubDatabase, schema_root_01) -> Node:
        """Create a device template."""
        template_schema = registry.schema.get_node_schema(name="TemplateTestingDevice", duplicate=False)
        device_template = await Node.init(db=db, schema=template_schema)
        await device_template.new(
            db=db,
            template_name="juniper_mx204",
            manufacturer="Juniper",
            model="MX204",
            weight=8,
        )
        await device_template.save(db=db)
        return device_template

    async def test_step_01_assign_profile_to_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_template: Node,
        device_profile: Node,
    ) -> None:
        """Test assigning a profile to a template via GraphQL."""
        mutation = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingDeviceUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
                object {
                    id
                    profiles {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                    airflow {
                        value
                        is_from_profile
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        source { id }
                    }
                    manufacturer {
                        value
                        is_from_profile
                        source { id }
                    }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": device_template.id,
                "profile_id": device_profile.id,
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["TemplateTestingDeviceUpdate"]["ok"] is True
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]
        assert len(obj["profiles"]["edges"]) == 1
        assert obj["profiles"]["edges"][0]["node"]["id"] == device_profile.id

        # Profile values should be applied to template
        assert obj["airflow"]["value"] == "Front to rear"
        assert obj["airflow"]["is_from_profile"] is True
        assert obj["airflow"]["source"]["id"] == device_profile.id

        assert obj["height"]["value"] == 1
        assert obj["height"]["is_from_profile"] is True
        assert obj["height"]["source"]["id"] == device_profile.id

        # Template's own value should remain
        assert obj["manufacturer"]["value"] == "Juniper"
        assert obj["manufacturer"]["is_from_profile"] is False
        assert obj["manufacturer"]["source"] is None

    async def test_step_02_create_node_from_template_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_template: Node,
        device_profile: Node,
    ) -> None:
        """Test creating a node from a template that has a profile assigned."""
        mutation = """
        mutation($template_id: String!) {
            TestingDeviceCreate(data: {
                name: {value: "router-01"},
                object_template: {id: $template_id}
            }) {
                ok
                object {
                    id
                    name { value }
                    manufacturer {
                        value
                        source { id }
                    }
                    model {
                        value
                        source { id }
                    }
                    weight {
                        value
                        source { id }
                    }
                    airflow {
                        value
                        source { id }
                        is_from_profile
                    }
                    height {
                        value
                        source { id }
                        is_from_profile
                    }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": device_template.id,
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["TestingDeviceCreate"]["ok"] is True
        obj = result.data["TestingDeviceCreate"]["object"]

        # Node should get name from user input
        assert obj["name"]["value"] == "router-01"

        # Node should get manufacturer, model, weight from template
        assert obj["manufacturer"]["value"] == "Juniper"
        assert obj["manufacturer"]["source"]["id"] == device_template.id

        assert obj["model"]["value"] == "MX204"
        assert obj["model"]["source"]["id"] == device_template.id

        assert obj["weight"]["value"] == 8
        assert obj["weight"]["source"]["id"] == device_template.id

        # Node should get airflow and height from profile (not template)
        assert obj["airflow"]["value"] == "Front to rear"
        assert obj["airflow"]["source"]["id"] == device_profile.id
        assert obj["airflow"]["is_from_profile"] is True

        assert obj["height"]["value"] == 1
        assert obj["height"]["source"]["id"] == device_profile.id
        assert obj["height"]["is_from_profile"] is True

    async def test_step_03_template_profile_precedence_over_template_value(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_profile: Node,
    ) -> None:
        """Test that profile values override template's own values."""
        # Create a new template with its own airflow value
        template_schema = registry.schema.get_node_schema(name="TemplateTestingDevice", duplicate=False)
        template_with_value = await Node.init(db=db, schema=template_schema)
        await template_with_value.new(
            db=db,
            template_name="arista_7280",
            manufacturer="Arista",
            model="7280SR",
            airflow="Rear to front",  # Template has its own airflow
            weight=10,
        )
        await template_with_value.save(db=db)

        # Assign profile to template
        mutation = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingDeviceUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
                object {
                    id
                    airflow {
                        value
                        is_from_profile
                        source { id }
                    }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": template_with_value.id,
                "profile_id": device_profile.id,
            },
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]

        # Profile value should override template's own value
        assert obj["airflow"]["value"] == "Front to rear"  # From profile, not "Rear to front" from template
        assert obj["airflow"]["is_from_profile"] is True
        assert obj["airflow"]["source"]["id"] == device_profile.id

        # Verify via direct database query
        retrieved_template = await NodeManager.get_one(
            db=db, id=template_with_value.id, include_metadata=MetadataOptions.SOURCE
        )
        assert retrieved_template.airflow.value == "Front to rear"
        assert retrieved_template.airflow.is_from_profile is True
        assert retrieved_template.airflow.source_id == device_profile.id

    async def test_step_04_multiple_profiles_on_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_profile: Node,
    ) -> None:
        """Test template with multiple profiles respects priority."""
        # Create a second profile with lower priority (higher number)
        profile_schema = registry.schema.get_node_schema(name="ProfileTestingDevice", duplicate=False)
        device_profile_2 = await Node.init(db=db, schema=profile_schema)
        await device_profile_2.new(
            db=db,
            profile_name="low_density_profile",
            profile_priority=200,
            airflow="Rear to front",
            weight=15,
        )
        await device_profile_2.save(db=db)

        # Create template
        template_schema = registry.schema.get_node_schema(name="TemplateTestingDevice", duplicate=False)
        template = await Node.init(db=db, schema=template_schema)
        await template.new(
            db=db,
            template_name="multi_profile_template",
            manufacturer="Cisco",
        )
        await template.save(db=db)

        # Assign both profiles
        mutation = """
        mutation($template_id: String!, $profile1_id: String!, $profile2_id: String!) {
            TemplateTestingDeviceUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile1_id}, {id: $profile2_id}]
            }) {
                ok
                object {
                    id
                    airflow {
                        value
                        source { id }
                    }
                    weight {
                        value
                        source { id }
                    }
                    height {
                        value
                        source { id }
                    }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": template.id,
                "profile1_id": device_profile.id,  # priority 100
                "profile2_id": device_profile_2.id,  # priority 200
            },
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]

        # Higher priority profile (lower number) should win for airflow
        assert obj["airflow"]["value"] == "Front to rear"
        assert obj["airflow"]["source"]["id"] == device_profile.id

        # Only profile 2 has weight, so it should be used
        assert obj["weight"]["value"] == 15
        assert obj["weight"]["source"]["id"] == device_profile_2.id

        # Only profile 1 has height, so it should be used
        assert obj["height"]["value"] == 1
        assert obj["height"]["source"]["id"] == device_profile.id

    async def test_step_05_sdk_create_template_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_profile: Node,
        client: InfrahubClient,
    ) -> None:
        """Test creating and managing templates with profiles via SDK."""
        # Create template via SDK
        template = await client.create(
            kind="TemplateTestingDevice",
            template_name="sdk_template",
            manufacturer="Dell",
            model="S5248F",
            profiles=[device_profile.id],
        )
        await template.save()

        # Retrieve and verify
        retrieved_template = await client.get(
            kind="TemplateTestingDevice",
            template_name__value="sdk_template",
            property=True,
        )
        await retrieved_template.profiles.fetch()

        assert retrieved_template.profiles.peer_ids == [device_profile.id]
        assert retrieved_template.airflow.value == "Front to rear"
        assert retrieved_template.airflow.is_from_profile is True
        assert retrieved_template.airflow.source.id == device_profile.id
        assert retrieved_template.height.value == 1
        assert retrieved_template.height.is_from_profile is True
        assert retrieved_template.height.source.id == device_profile.id

        # Create node from template via SDK
        device = await client.create(
            kind="TestingDevice",
            name="sdk-device-01",
            object_template=retrieved_template.id,
        )
        await device.save()

        # Verify node got profile values
        retrieved_device = await client.get(
            kind="TestingDevice",
            name__value="sdk-device-01",
            property=True,
        )

        assert retrieved_device.airflow.value == "Front to rear"
        assert retrieved_device.airflow.source.id == device_profile.id
        assert retrieved_device.height.value == 1
        assert retrieved_device.height.source.id == device_profile.id
        assert retrieved_device.manufacturer.value == "Dell"
        assert retrieved_device.manufacturer.source.id == retrieved_template.id
