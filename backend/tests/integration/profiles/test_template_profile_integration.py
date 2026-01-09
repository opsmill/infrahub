"""Integration tests for template profile support."""

import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import MetadataOptions, RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
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
    ) -> None:
        """Load the device schema with template and profile support, including template and profile schemas."""
        # When a schema with generate_template=True or generate_profile=True is loaded,
        # the system automatically creates the Template and Profile schemas
        schema_root = SchemaRoot(version="1.0", nodes=[device_schema_base])
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def device_profile(self, db: InfrahubDatabase, schema_root_01, default_branch: Branch) -> Node:
        """Create a device profile."""
        profile_schema = registry.schema.get_profile_schema(
            name="ProfileTestingDevice", branch=default_branch, duplicate=False
        )
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
    async def device_template(self, db: InfrahubDatabase, schema_root_01, default_branch: Branch) -> Node:
        """Create a device template."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
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

    @pytest.fixture(scope="class")
    async def device_template_with_profile(
        self, db: InfrahubDatabase, schema_root_01, default_branch: Branch, device_profile: Node
    ) -> Node:
        """Create a device template with an assigned profile."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
        device_template = await Node.init(db=db, schema=template_schema)
        await device_template.new(
            db=db,
            template_name="juniper_mx204_with_profile",
            manufacturer="Juniper",
            model="MX204",
            weight=8,
            profiles=[device_profile.id],
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
        """Test assigning a profile to a template via GraphQL.

        Logic: Template has manufacturer=Juniper, model=MX204, weight=8 explicitly set.
        Profile has airflow and height set.
        Expected: Profile values used for airflow/height (were default), template values remain for explicitly set attributes.
        """
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
                        is_default
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                    manufacturer {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                    weight {
                        value
                        is_from_profile
                        is_default
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

        # Profile values should be applied for attributes using defaults
        assert obj["airflow"] == {
            "value": "Front to rear",
            "is_from_profile": True,
            "is_default": False,
            "source": {"id": device_profile.id},
        }

        assert obj["height"] == {
            "value": 1,
            "is_from_profile": True,
            "is_default": False,
            "source": {"id": device_profile.id},
        }

        # Template's explicitly set values should remain unchanged
        assert obj["manufacturer"] == {
            "value": "Juniper",
            "is_from_profile": False,
            "is_default": False,
            "source": None,
        }

        assert obj["weight"] == {
            "value": 8,
            "is_from_profile": False,
            "is_default": False,
            "source": None,
        }

    async def test_step_02_create_node_from_template_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_template_with_profile: Node,
        device_profile: Node,
    ) -> None:
        """Test creating a node from a template that has a profile assigned.

        Logic: When node is created from template with profiles, the profiles are inherited.
        - Explicitly set template values → source is template
        - Profile values → source is profile (profiles inherited from template)
        """
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
                        is_from_profile
                    }
                    model {
                        value
                        source { id }
                        is_from_profile
                    }
                    weight {
                        value
                        source { id }
                        is_from_profile
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
                "template_id": device_template_with_profile.id,
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["TestingDeviceCreate"]["ok"] is True
        obj = result.data["TestingDeviceCreate"]["object"]

        # Node should get name from user input
        assert obj["name"]["value"] == "router-01"

        # Node should get manufacturer, model, weight from template (template explicitly set these)
        assert obj["manufacturer"]["value"] == "Juniper"
        assert obj["manufacturer"]["source"]["id"] == device_template_with_profile.id
        assert obj["manufacturer"]["is_from_profile"] is False

        assert obj["model"]["value"] == "MX204"
        assert obj["model"]["source"]["id"] == device_template_with_profile.id
        assert obj["model"]["is_from_profile"] is False

        assert obj["weight"]["value"] == 8
        assert obj["weight"]["source"]["id"] == device_template_with_profile.id
        assert obj["weight"]["is_from_profile"] is False

        # Node inherits profiles from template, so airflow and height come directly from profile
        assert obj["airflow"]["value"] == "Front to rear"
        assert obj["airflow"]["source"]["id"] == device_profile.id
        assert obj["airflow"]["is_from_profile"] is True

        assert obj["height"]["value"] == 1
        assert obj["height"]["source"]["id"] == device_profile.id
        assert obj["height"]["is_from_profile"] is True

    async def test_step_03_template_explicit_value_not_overridden_by_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_profile: Node,
    ) -> None:
        """Test that explicitly set template values are NOT overridden by profile values.

        Logic: If value explicitly set on template → Use template value (even if profile has different value).
        """
        # Create a new template with its own airflow value explicitly set
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
        template_with_value = await Node.init(db=db, schema=template_schema)
        await template_with_value.new(
            db=db,
            template_name="arista_7280",
            manufacturer="Arista",
            model="7280SR",
            airflow="Rear to front",  # Template has its own airflow explicitly set
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
                        is_default
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        is_default
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

        # Template's explicitly set value should NOT be overridden by profile
        assert obj["airflow"]["value"] == "Rear to front"  # From template, not profile
        assert obj["airflow"]["is_from_profile"] is False
        assert obj["airflow"]["is_default"] is False
        assert obj["airflow"]["source"] is None

        # Height was using default, so profile value should be used
        assert obj["height"]["value"] == 1
        assert obj["height"]["is_from_profile"] is True
        assert obj["height"]["is_default"] is False
        assert obj["height"]["source"]["id"] == device_profile.id

        # Verify via direct database query
        retrieved_template = await NodeManager.get_one(
            db=db,
            id=template_with_value.id,
            include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE),
        )
        assert retrieved_template.airflow.value == "Rear to front"
        assert retrieved_template.airflow.is_from_profile is False
        assert retrieved_template.airflow.is_default is False
        assert retrieved_template.airflow.source_id is None

        assert retrieved_template.height.value == 1
        assert retrieved_template.height.is_from_profile is True
        assert retrieved_template.height.is_default is False
        assert retrieved_template.height.source_id == device_profile.id

    async def test_step_04_multiple_profiles_on_template(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_profile: Node,
    ) -> None:
        """Test template with multiple profiles respects priority (lowest number = highest priority)."""
        # Create a second profile with lower priority (higher number)
        profile_schema = registry.schema.get_profile_schema(
            name="ProfileTestingDevice", branch=default_branch, duplicate=False
        )
        device_profile_2 = await Node.init(db=db, schema=profile_schema)
        await device_profile_2.new(
            db=db,
            profile_name="low_density_profile",
            profile_priority=200,  # Lower priority than device_profile (100)
            airflow="Rear to front",
            weight=15,
        )
        await device_profile_2.save(db=db)

        # Create template without explicit values
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
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
                        is_from_profile
                        is_default
                        source { id }
                    }
                    weight {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        is_default
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
                "profile1_id": device_profile.id,  # priority 100 (higher priority)
                "profile2_id": device_profile_2.id,  # priority 200 (lower priority)
            },
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]

        # Higher priority profile (lower number = 100) should win for airflow
        assert obj["airflow"]["value"] == "Front to rear"
        assert obj["airflow"]["is_from_profile"] is True
        assert obj["airflow"]["is_default"] is False
        assert obj["airflow"]["source"]["id"] == device_profile.id

        # Only profile 2 has weight, so it should be used
        assert obj["weight"]["value"] == 15
        assert obj["weight"]["is_from_profile"] is True
        assert obj["weight"]["is_default"] is False
        assert obj["weight"]["source"]["id"] == device_profile_2.id

        # Only profile 1 has height, so it should be used
        assert obj["height"]["value"] == 1
        assert obj["height"]["is_from_profile"] is True
        assert obj["height"]["is_default"] is False
        assert obj["height"]["source"]["id"] == device_profile.id

    async def test_step_04b_template_update_overrides_profile_value(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        """Test that updating a template attribute explicitly overrides profile value.

        Logic: When template updates an attribute that was using profile value,
        the explicit value should override the profile.
        """
        # Create profile
        profile_schema = registry.schema.get_profile_schema(
            name="ProfileTestingDevice", branch=default_branch, duplicate=False
        )
        test_profile = await Node.init(db=db, schema=profile_schema)
        await test_profile.new(
            db=db,
            profile_name="test_override_profile",
            profile_priority=50,
            airflow="Profile airflow",
            height=99,
        )
        await test_profile.save(db=db)

        # Create template without explicit airflow/height values
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch, duplicate=False
        )
        test_template = await Node.init(db=db, schema=template_schema)
        await test_template.new(
            db=db,
            template_name="test_override_template",
            manufacturer="TestManufacturer",
        )
        await test_template.save(db=db)

        # Assign profile to template via GraphQL
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        assign_profile_mutation = """
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
                        is_default
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                }
            }
        }
        """

        result = await graphql(
            schema=gql_params.schema,
            source=assign_profile_mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_id": test_template.id, "profile_id": test_profile.id},
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]

        # Verify template uses profile values
        assert obj["airflow"]["value"] == "Profile airflow"
        assert obj["airflow"]["is_from_profile"] is True
        assert obj["airflow"]["is_default"] is False
        assert obj["airflow"]["source"]["id"] == test_profile.id
        assert obj["height"]["value"] == 99
        assert obj["height"]["is_from_profile"] is True
        assert obj["height"]["is_default"] is False
        assert obj["height"]["source"]["id"] == test_profile.id

        # Now update template to set airflow explicitly
        update_mutation = """
        mutation($template_id: String!) {
            TemplateTestingDeviceUpdate(data: {
                id: $template_id,
                airflow: {value: "Explicitly set airflow"}
            }) {
                ok
                object {
                    id
                    airflow {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                    height {
                        value
                        is_from_profile
                        is_default
                        source { id }
                    }
                }
            }
        }
        """

        result = await graphql(
            schema=gql_params.schema,
            source=update_mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_id": test_template.id},
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingDeviceUpdate"]["object"]

        # Airflow should now use explicitly set value, not profile
        assert obj["airflow"]["value"] == "Explicitly set airflow"
        assert obj["airflow"]["is_from_profile"] is False
        assert obj["airflow"]["is_default"] is False
        assert obj["airflow"]["source"] is None

        # Height should still use profile value
        assert obj["height"]["value"] == 99
        assert obj["height"]["is_from_profile"] is True
        assert obj["height"]["is_default"] is False
        assert obj["height"]["source"]["id"] == test_profile.id

        # Verify via database
        retrieved = await NodeManager.get_one(
            db=db, id=test_template.id, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
        )
        assert retrieved.airflow.value == "Explicitly set airflow"
        assert retrieved.airflow.is_from_profile is False
        assert retrieved.airflow.source_id is None
        assert retrieved.height.value == 99
        assert retrieved.height.is_from_profile is True
        assert retrieved.height.source_id == test_profile.id

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

        # Verify node got values (profiles inherited from template)
        retrieved_device = await client.get(
            kind="TestingDevice",
            name__value="sdk-device-01",
            property=True,
        )

        # Template values come from template, profile values come from profile (inherited)
        assert retrieved_device.airflow.value == "Front to rear"
        assert retrieved_device.airflow.source.id == device_profile.id  # Profile inherited from template
        assert retrieved_device.airflow.is_from_profile is True
        assert retrieved_device.height.value == 1
        assert retrieved_device.height.source.id == device_profile.id  # Profile inherited from template
        assert retrieved_device.height.is_from_profile is True
        assert retrieved_device.manufacturer.value == "Dell"
        assert retrieved_device.manufacturer.source.id == retrieved_template.id  # Explicitly set on template


class TestTemplateProfileWithComponents(TestInfrahubApp):
    """Test template profile support with component relationships."""

    @pytest.fixture(scope="class")
    def interface_schema(self) -> NodeSchema:
        """Create an interface schema with template and profile support."""
        return NodeSchema(
            name="Interface",
            namespace="Testing",
            generate_template=True,
            generate_profile=True,
            label="Interface",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=False),
                AttributeSchema(name="enabled", kind="Boolean", default_value=True, optional=True),
                AttributeSchema(name="mtu", kind="Number", optional=True),
                AttributeSchema(name="speed", kind="Text", optional=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="device",
                    kind=RelationshipKind.PARENT,
                    peer="TestingDeviceWithInterfaces",
                    cardinality=RelationshipCardinality.ONE,
                    optional=False,
                )
            ],
        )

    @pytest.fixture(scope="class")
    def device_with_interfaces_schema(self, interface_schema: NodeSchema) -> NodeSchema:
        """Create a device schema with component interfaces."""
        return NodeSchema(
            name="DeviceWithInterfaces",
            namespace="Testing",
            generate_template=True,
            generate_profile=True,
            label="Device with Interfaces",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="manufacturer", kind="Text", optional=True),
                AttributeSchema(name="model", kind="Text", optional=True),
                AttributeSchema(name="role", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="interfaces",
                    kind=RelationshipKind.COMPONENT,
                    peer="TestingInterface",
                    cardinality=RelationshipCardinality.MANY,
                    optional=True,
                )
            ],
        )

    @pytest.fixture(scope="class")
    async def component_schema_root(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        interface_schema: NodeSchema,
        device_with_interfaces_schema: NodeSchema,
    ) -> None:
        """Load schemas with component relationships."""
        schema_root = SchemaRoot(version="1.0", nodes=[interface_schema, device_with_interfaces_schema])
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def interface_profile(self, db: InfrahubDatabase, component_schema_root, default_branch: Branch) -> Node:
        """Create an interface profile."""
        profile_schema = registry.schema.get_profile_schema(
            name="ProfileTestingInterface", branch=default_branch, duplicate=False
        )
        interface_profile = await Node.init(db=db, schema=profile_schema)
        await interface_profile.new(
            db=db,
            profile_name="high_speed_interface",
            profile_priority=100,
            mtu=9000,
            speed="10G",
            enabled=True,
        )
        await interface_profile.save(db=db)
        return interface_profile

    @pytest.fixture(scope="class")
    async def device_component_profile(
        self, db: InfrahubDatabase, component_schema_root, default_branch: Branch
    ) -> Node:
        """Create a device profile."""
        profile_schema = registry.schema.get_profile_schema(
            name="ProfileTestingDeviceWithInterfaces", branch=default_branch, duplicate=False
        )
        device_profile = await Node.init(db=db, schema=profile_schema)
        await device_profile.new(
            db=db,
            profile_name="spine_device",
            profile_priority=100,
            role="spine",
        )
        await device_profile.save(db=db)
        return device_profile

    async def test_step_01_create_component_templates_with_profiles(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        interface_profile: Node,
    ) -> Node:
        """Test creating component templates (interfaces) with profiles."""

        # Create device template with component interface templates
        device_template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDeviceWithInterfaces", branch=default_branch, duplicate=False
        )

        device_template = await Node.init(db=db, schema=device_template_schema)
        await device_template.new(db=db, template_name="spine_switch_template", manufacturer="Arista", model="7280R")
        await device_template.save(db=db)
        # Create interface templates with profile via GraphQL
        # This ensures profiles are applied through the same flow as production
        mutation = """
        mutation($profile_id: String!, $device_template: String!) {
            TemplateTestingInterfaceCreate(data: {
                template_name: {value: "eth0_template"},
                name: {value: "eth0"},
                description: {value: "Management Interface"},
                profiles: [{id: $profile_id}],
                device: {id: $device_template}
            }) {
                ok
                object {
                    id
                    mtu { value is_from_profile source { id } }
                    speed { value is_from_profile source { id } }
                    enabled { value is_from_profile source { id } }
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
                "profile_id": interface_profile.id,
                "device_template": device_template.id,
            },
        )

        assert result.errors is None
        assert result.data
        obj = result.data["TemplateTestingInterfaceCreate"]["object"]

        # Verify profile was applied to interface template
        assert obj["mtu"]["value"] == 9000
        assert obj["mtu"]["is_from_profile"] is True
        assert obj["mtu"]["source"]["id"] == interface_profile.id
        assert obj["speed"]["value"] == "10G"
        assert obj["speed"]["is_from_profile"] is True
        assert obj["enabled"]["value"] is True
        assert obj["enabled"]["is_from_profile"] is True

        # Verify via database retrieval
        template_id = obj["id"]
        retrieved = await NodeManager.get_one(
            db=db, id=template_id, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
        )
        assert retrieved.mtu.value == 9000
        assert retrieved.mtu.is_from_profile is True
        assert retrieved.mtu.source_id == interface_profile.id
        assert retrieved.speed.value == "10G"
        assert retrieved.enabled.value is True
        return retrieved

    async def test_step_02_create_device_template_with_component_templates(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        interface_profile: Node,
        device_component_profile: Node,
    ) -> dict[str, str]:
        """Test creating a device template that references component templates."""

        # Create device template with component interface templates
        device_template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDeviceWithInterfaces", branch=default_branch, duplicate=False
        )

        device_template = await Node.init(db=db, schema=device_template_schema)
        await device_template.new(db=db, template_name="spine_switch_template", manufacturer="Arista", model="7280R")
        await device_template.save(db=db)

        # Create interface templates with profiles
        interface_template_schema = registry.schema.get_template_schema(
            name="TemplateTestingInterface", branch=default_branch, duplicate=False
        )

        eth0_template = await Node.init(db=db, schema=interface_template_schema)
        await eth0_template.new(
            db=db, template_name="mgmt_eth0", name="eth0", description="Management Interface", device=device_template.id
        )
        await eth0_template.save(db=db)

        # Assign profile to interface template via mutation
        mutation_assign_profile = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingInterfaceUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": eth0_template.id,
                "profile_id": interface_profile.id,
            },
        )
        assert result.errors is None

        eth1_template = await Node.init(db=db, schema=interface_template_schema)
        await eth1_template.new(
            db=db, template_name="uplink_eth1", name="eth1", description="Uplink Interface", device=device_template.id
        )
        await eth1_template.save(db=db)

        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": eth1_template.id,
                "profile_id": interface_profile.id,
            },
        )
        assert result.errors is None

        # Assign profile to device template
        mutation_assign_device_profile = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingDeviceWithInterfacesUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
            }
        }
        """

        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_device_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": device_template.id,
                "profile_id": device_component_profile.id,
            },
        )
        assert result.errors is None

        # Verify device template has profile applied
        retrieved_device_template = await NodeManager.get_one(
            db=db, id=device_template.id, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
        )
        assert retrieved_device_template.role.value == "spine"
        assert retrieved_device_template.role.is_from_profile is True
        assert retrieved_device_template.role.source_id == device_component_profile.id

        return {
            "device_template_id": device_template.id,
            "eth0_template_id": eth0_template.id,
            "eth1_template_id": eth1_template.id,
        }

    async def test_step_03_create_device_from_template_with_component_profiles(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        interface_profile: Node,
        device_component_profile: Node,
    ) -> None:
        """Test creating a device from a template that has component templates with profiles.

        This verifies that when a device is created from a template:
        1. The device gets values from its template's profile
        2. Component interfaces are created from interface templates
        3. Component interfaces get values from their template's profiles
        """
        # Create device template with component templates
        device_template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDeviceWithInterfaces", branch=default_branch, duplicate=False
        )

        device_template = await Node.init(db=db, schema=device_template_schema)
        await device_template.new(
            db=db,
            template_name="full_device_template",
            manufacturer="Cisco",
            model="Nexus 9000",
        )
        await device_template.save(db=db)

        # Create interface templates with profiles
        interface_template_schema = registry.schema.get_template_schema(
            name="TemplateTestingInterface", branch=default_branch, duplicate=False
        )

        eth0_template = await Node.init(db=db, schema=interface_template_schema)
        await eth0_template.new(
            db=db,
            template_name="component_eth0",
            name="eth0",
            description="Component Management",
            device=device_template,
        )
        await eth0_template.save(db=db)

        # Assign profile via GraphQL mutation
        mutation_assign_profile = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingInterfaceUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": eth0_template.id,
                "profile_id": interface_profile.id,
            },
        )
        assert result.errors is None

        eth1_template = await Node.init(db=db, schema=interface_template_schema)
        await eth1_template.new(
            db=db, template_name="component_eth1", name="eth1", description="Component Uplink", device=device_template
        )
        await eth1_template.save(db=db)

        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": eth1_template.id,
                "profile_id": interface_profile.id,
            },
        )
        assert result.errors is None

        # Assign device profile
        mutation_assign_device_profile = """
        mutation($template_id: String!, $profile_id: String!) {
            TemplateTestingDeviceWithInterfacesUpdate(data: {
                id: $template_id,
                profiles: [{id: $profile_id}]
            }) {
                ok
            }
        }
        """

        result = await graphql(
            schema=gql_params.schema,
            source=mutation_assign_device_profile,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "template_id": device_template.id,
                "profile_id": device_component_profile.id,
            },
        )
        assert result.errors is None

        # Create device from template via GraphQL
        mutation = """
        mutation($template_id: String!) {
            TestingDeviceWithInterfacesCreate(data: {
                name: {value: "spine-01"},
                object_template: {id: $template_id}
            }) {
                ok
                object {
                    id
                    name { value }
                    manufacturer { value source { id } }
                    model { value source { id } }
                    role { value is_from_profile source { id } }
                    interfaces {
                        edges {
                            node {
                                id
                                name { value }
                                description { value source { id } }
                                mtu { value is_from_profile source { id } }
                                speed { value is_from_profile source { id } }
                                enabled { value is_from_profile source { id } }
                            }
                        }
                    }
                }
            }
        }
        """

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
        obj = result.data["TestingDeviceWithInterfacesCreate"]["object"]

        # Verify device properties
        assert obj["name"]["value"] == "spine-01"
        assert obj["manufacturer"]["value"] == "Cisco"
        assert obj["manufacturer"]["source"]["id"] == device_template.id
        assert obj["model"]["value"] == "Nexus 9000"
        assert obj["model"]["source"]["id"] == device_template.id

        # Device role: check value and source
        # Note: Role comes from template's profile, actual source depends on implementation
        assert obj["role"]["value"] == "spine"
        assert obj["role"]["source"]["id"] == device_component_profile.id

        # Verify component interfaces were created
        interfaces = obj["interfaces"]["edges"]
        assert len(interfaces) == 2

        # Verify interfaces got values (profiles inherited from their templates)
        interface_names = {iface["node"]["name"]["value"] for iface in interfaces}
        assert interface_names == {"eth0", "eth1"}

        for iface in interfaces:
            iface_node = iface["node"]
            # Interface inherits profile from its template, so profile values come from profile
            assert iface_node["mtu"]["value"] == 9000
            assert iface_node["mtu"]["is_from_profile"] is True
            assert iface_node["mtu"]["source"]["id"] == interface_profile.id

            assert iface_node["speed"]["value"] == "10G"
            assert iface_node["speed"]["is_from_profile"] is True
            assert iface_node["speed"]["source"]["id"] == interface_profile.id

            assert iface_node["enabled"]["value"] is True
            assert iface_node["enabled"]["is_from_profile"] is True
            assert iface_node["enabled"]["source"]["id"] == interface_profile.id

            # Description was explicitly set on template, comes from template
            if iface_node["name"]["value"] == "eth0":
                assert iface_node["description"]["value"] == "Component Management"
                assert iface_node["description"]["source"]["id"] == eth0_template.id
            else:
                assert iface_node["description"]["value"] == "Component Uplink"
                assert iface_node["description"]["source"]["id"] == eth1_template.id

        # Verify via direct database query
        device_id = obj["id"]
        retrieved_device = await NodeManager.get_one(
            db=db, id=device_id, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
        )

        assert retrieved_device.role.value == "spine"
        assert retrieved_device.role.is_from_profile is True
        assert retrieved_device.role.source_id == device_component_profile.id

        # Get and verify interfaces
        interfaces_rel = await retrieved_device.interfaces.get_peers(
            db=db, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
        )
        assert len(interfaces_rel) == 2

        for interface in interfaces_rel.values():
            await interface.mtu.get_source(db=db)
            assert interface.mtu.value == 9000
            assert interface.mtu.is_from_profile is True
            assert interface.mtu.source_id == interface_profile.id
            await interface.speed.get_source(db=db)
            assert interface.speed.value == "10G"
            assert interface.speed.is_from_profile is True
            assert interface.speed.source_id == interface_profile.id
            await interface.enabled.get_source(db=db)
            assert interface.enabled.value is True
            assert interface.enabled.is_from_profile is True
            assert interface.enabled.source_id == interface_profile.id
