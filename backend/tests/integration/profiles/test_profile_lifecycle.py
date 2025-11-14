import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import HashableModelState, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

PERSON_VALUES = """
        object {
            id
            profiles { edges { node { id } } }
            name {
                value
                source { id }
                is_from_profile
                is_default
            }
            height {
                value
                source { id }
                is_from_profile
                is_default
            }
            weight {
                value
                source { id }
                is_from_profile
                is_default
            }
            eye_color {
                value
                source { id }
                is_from_profile
                is_default
            }
            description {
                value
                source { id }
                is_from_profile
                is_default
            }
            nothing {
                value
                source { id }
                is_from_profile
                is_default
            }
            size {
                value
                source { id }
                is_from_profile
                is_default
            }
            shape {
                value
                source { id }
                is_from_profile
                is_default
            }
            is_alive {
                value
                source { id }
                is_from_profile
                is_default
            }
            lifespan {
                value
                source { id }
                is_from_profile
                is_default
            }
            generic_nothing {
                value
                source { id }
                is_from_profile
                is_default
            }
        }
"""

PERSON_UPDATE_QUERY = """
mutation ($update_data: PretendPersonUpdateInput!) {
    PretendPersonUpdate(data: $update_data) {
        ok
        %(person_values)s
    }
}
""" % {"person_values": PERSON_VALUES}


class TestProfileLifecycle(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def generic_schema_base(self) -> GenericSchema:
        return GenericSchema(
            name="Lifeform",
            namespace="Pretend",
            attributes=[
                # size will become optional later to test that it is added to profiles
                AttributeSchema(name="size", kind="TextArea", optional=False),
                # shape will become mandatory later to test that it is removed from profiles
                AttributeSchema(name="shape", kind="Text", optional=True),
                # is_alive will become read_only=False later to test that it is added to profiles
                AttributeSchema(name="is_alive", kind="Boolean", optional=True, read_only=True),
                # lifespan will become read_only=True later to test that it is removed from profiles
                AttributeSchema(name="lifespan", kind="Number", optional=True),
                # generic_nothing will be removed later to test that it is removed from profiles
                AttributeSchema(name="generic_nothing", kind="TextArea", optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    def person_schema_base(self) -> NodeSchema:
        return NodeSchema(
            name="Person",
            namespace="Pretend",
            inherit_from=["PretendLifeform"],
            label="Person",
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                # weight will become optional later to test that it is added to profiles
                AttributeSchema(name="weight", kind="Number", optional=False),
                # height will become mandatory later to test that it is removed from profiles
                AttributeSchema(name="height", kind="Number", optional=True),
                # eye_color will become read_only=False later to test that it is added to profiles
                AttributeSchema(name="eye_color", kind="Text", optional=True, read_only=True),
                # description will become read_only=True later to test that it is removed from profiles
                AttributeSchema(name="description", kind="TextArea", optional=True, default_value="placeholder"),
                # nothing will be removed later to test that it is removed from profiles
                AttributeSchema(name="nothing", kind="TextArea", optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    async def schema_root_01(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        generic_schema_base: GenericSchema,
        person_schema_base: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(version="1.0", generics=[generic_schema_base], nodes=[person_schema_base])
        await load_schema(db=db, schema=schema_root, branch_name=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def generic_schema_add_attributes_to_profiles(self, generic_schema_base: GenericSchema) -> GenericSchema:
        updated_generic_schema = generic_schema_base.model_copy(deep=True)
        size_attribute = updated_generic_schema.get_attribute("size")
        size_attribute.optional = True
        is_alive_attribute = updated_generic_schema.get_attribute("is_alive")
        is_alive_attribute.read_only = False
        # new attribute that should be added to profiles
        updated_generic_schema.attributes.append(AttributeSchema(name="value", kind="Number", optional=True))
        # new attribute that should NOT be added to profiles
        updated_generic_schema.attributes.append(
            AttributeSchema(name="generic_not_for_profiles", kind="Text", optional=True, read_only=True)
        )
        return updated_generic_schema

    @pytest.fixture(scope="class")
    async def person_schema_add_attributes_to_profiles(self, person_schema_base: NodeSchema) -> NodeSchema:
        updated_person_schema = person_schema_base.model_copy(deep=True)
        weight_attribute = updated_person_schema.get_attribute("weight")
        weight_attribute.optional = True
        eye_color_attribute = updated_person_schema.get_attribute("eye_color")
        eye_color_attribute.read_only = False
        # new attribute that should be added to profiles
        updated_person_schema.attributes.append(AttributeSchema(name="age", kind="Number", optional=True))
        # new attribute that should NOT be added to profiles
        updated_person_schema.attributes.append(
            AttributeSchema(name="not_for_profiles", kind="Text", optional=True, read_only=True)
        )
        return updated_person_schema

    @pytest.fixture(scope="class")
    async def schema_root_02(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        generic_schema_add_attributes_to_profiles: GenericSchema,
        person_schema_add_attributes_to_profiles: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(
            version="1.0",
            generics=[generic_schema_add_attributes_to_profiles],
            nodes=[person_schema_add_attributes_to_profiles],
        )
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=default_branch.name)
        assert response.schema_updated
        assert not response.errors

    @pytest.fixture(scope="class")
    async def generic_schema_remove_attributes_from_profiles(
        self, default_branch: Branch, generic_schema_add_attributes_to_profiles: GenericSchema, client: InfrahubClient
    ) -> GenericSchema:
        current_generic_schema = await client.schema.get(
            kind="ProfilePretendLifeform", branch=default_branch.name, refresh=True
        )
        current_generic_nothing_attribute = current_generic_schema.get_attribute("generic_nothing")
        updated_generic_schema = generic_schema_add_attributes_to_profiles.model_copy(deep=True)
        shape_attribute = updated_generic_schema.get_attribute("shape")
        shape_attribute.optional = False
        lifespan_attribute = updated_generic_schema.get_attribute("lifespan")
        lifespan_attribute.read_only = True
        generic_nothing_attribute = updated_generic_schema.get_attribute("generic_nothing")
        generic_nothing_attribute.state = HashableModelState.ABSENT
        generic_nothing_attribute.id = current_generic_nothing_attribute.id
        return updated_generic_schema

    @pytest.fixture(scope="class")
    async def person_schema_remove_attributes_from_profiles(
        self, default_branch: Branch, person_schema_add_attributes_to_profiles: NodeSchema, client: InfrahubClient
    ) -> NodeSchema:
        current_person_schema = await client.schema.get(
            kind="ProfilePretendPerson", branch=default_branch.name, refresh=True
        )
        current_nothing_attribute = current_person_schema.get_attribute("nothing")

        updated_person_schema = person_schema_add_attributes_to_profiles.model_copy(deep=True)
        height_attribute = updated_person_schema.get_attribute("height")
        height_attribute.optional = False
        description_attribute = updated_person_schema.get_attribute("description")
        description_attribute.read_only = True
        nothing_attribute = updated_person_schema.get_attribute("nothing")
        nothing_attribute.state = HashableModelState.ABSENT
        nothing_attribute.id = current_nothing_attribute.id
        return updated_person_schema

    @pytest.fixture(scope="class")
    async def schema_root_03(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        generic_schema_remove_attributes_from_profiles: GenericSchema,
        person_schema_remove_attributes_from_profiles: NodeSchema,
        client: InfrahubClient,
    ) -> None:
        schema_root = SchemaRoot(
            version="1.0",
            generics=[generic_schema_remove_attributes_from_profiles],
            nodes=[person_schema_remove_attributes_from_profiles],
        )
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=default_branch.name)
        assert response.schema_updated
        assert not response.errors

    @pytest.fixture(scope="class")
    async def person_1(self, db: InfrahubDatabase, schema_root_01) -> Node:
        schema = registry.schema.get_node_schema(name="PretendPerson", duplicate=False)
        person_1 = await Node.init(db=db, schema=schema)
        await person_1.new(
            db=db,
            name="Starbuck",
            size="human",
            weight=70,
        )
        await person_1.save(db=db)
        return person_1

    @pytest.fixture(scope="class")
    async def lifeform_profile_1(self, db: InfrahubDatabase, schema_root_01) -> Node:
        lifeform_profile_1 = await Node.init(db=db, schema="ProfilePretendLifeform")
        await lifeform_profile_1.new(
            db=db,
            profile_name="lifeform-profile-one",
            profile_priority=3,
            shape="lifeform-profile-one shape",
            generic_nothing="lifeform-profile-one generic nothing",
        )
        await lifeform_profile_1.save(db=db)
        return lifeform_profile_1

    @pytest.fixture(scope="class")
    async def person_profile_1(self, db: InfrahubDatabase, schema_root_01) -> Node:
        person_profile_1 = await Node.init(db=db, schema="ProfilePretendPerson")
        await person_profile_1.new(
            db=db,
            profile_name="profile-one",
            profile_priority=10,
            height=167,
            description="profile-one description",
            lifespan=85,
            nothing="profile-one nothing",
            generic_nothing="profile-one generic nothing",
        )
        await person_profile_1.save(db=db)
        return person_profile_1

    async def test_step_01_one_person_no_profile(
        self, db: InfrahubDatabase, schema_root_01, person_1, person_profile_1, client: InfrahubClient
    ) -> None:
        retrieved_person = await client.get(kind="PretendPerson", id=person_1.id, property=True)

        assert retrieved_person.profiles.peer_ids == []
        assert retrieved_person.name.value == "Starbuck"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value is None
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source is None
        assert retrieved_person.height.is_default is True
        assert retrieved_person.weight.value == 70
        assert retrieved_person.weight.is_from_profile is False
        assert retrieved_person.weight.source is None
        assert retrieved_person.weight.is_default is False
        assert retrieved_person.size.value == "human"
        assert retrieved_person.size.is_from_profile is False
        assert retrieved_person.size.source is None
        assert retrieved_person.size.is_default is False

    async def test_step_02_one_person_add_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PERSON_UPDATE_QUERY,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"update_data": {"id": person_1.id, "profiles": [{"id": person_profile_1.id}]}},
        )

        assert result.errors is None
        assert result.data
        assert result.data["PretendPersonUpdate"]["ok"] is True
        profiles = result.data["PretendPersonUpdate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["PretendPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {
            "value": "Starbuck",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["height"] == {
            "value": 167,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["weight"] == {
            "value": 70,
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["eye_color"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["description"] == {
            "value": "profile-one description",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["nothing"] == {
            "value": "profile-one nothing",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["size"] == {
            "value": "human",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["shape"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["is_alive"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["lifespan"] == {
            "value": 85,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["generic_nothing"] == {
            "value": "profile-one generic nothing",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }

        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id, include_metadata=MetadataOptions.SOURCE)
        assert retrieved_person.name.value == "Starbuck"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 167
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source_id == person_profile_1.id
        assert retrieved_person.height.is_default is False
        assert retrieved_person.weight.value == 70
        assert retrieved_person.weight.is_from_profile is False
        assert retrieved_person.weight.source_id is None
        assert retrieved_person.weight.is_default is False
        assert retrieved_person.eye_color.value is None
        assert retrieved_person.eye_color.is_from_profile is False
        assert retrieved_person.eye_color.source_id is None
        assert retrieved_person.eye_color.is_default is True
        assert retrieved_person.description.value == "profile-one description"
        assert retrieved_person.description.is_from_profile is True
        assert retrieved_person.description.source_id == person_profile_1.id
        assert retrieved_person.description.is_default is False
        assert retrieved_person.nothing.value == "profile-one nothing"
        assert retrieved_person.nothing.is_from_profile is True
        assert retrieved_person.nothing.source_id == person_profile_1.id
        assert retrieved_person.nothing.is_default is False
        assert retrieved_person.size.value == "human"
        assert retrieved_person.size.is_from_profile is False
        assert retrieved_person.size.source_id is None
        assert retrieved_person.size.is_default is False
        assert retrieved_person.shape.value is None
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source_id is None
        assert retrieved_person.shape.is_default is True
        assert retrieved_person.is_alive.value is None
        assert retrieved_person.is_alive.is_from_profile is False
        assert retrieved_person.is_alive.source_id is None
        assert retrieved_person.is_alive.is_default is True
        assert retrieved_person.lifespan.value == 85
        assert retrieved_person.lifespan.is_from_profile is True
        assert retrieved_person.lifespan.source_id == person_profile_1.id
        assert retrieved_person.lifespan.is_default is False
        assert retrieved_person.generic_nothing.value == "profile-one generic nothing"
        assert retrieved_person.generic_nothing.is_from_profile is True
        assert retrieved_person.generic_nothing.source_id == person_profile_1.id
        assert retrieved_person.generic_nothing.is_default is False

    async def test_step_03_create_person_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_profile_1,
    ) -> None:
        mutation = """
            mutation {
                PretendPersonCreate(data: {
                    name: {value: "Apollo"},
                    weight: {value: 85},
                    size: {value: "bigger human"}
                    shape: {value: "bipedal"}
                    profiles: [{ id: "%(profile_id)s"}]
                }) {
                    ok
                    %(person_values)s
                }
            }
        """ % {"profile_id": person_profile_1.id, "person_values": PERSON_VALUES}

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert result.errors is None
        assert result.data
        assert result.data["PretendPersonCreate"]["ok"] is True
        new_person_id = result.data["PretendPersonCreate"]["object"]["id"]
        profiles = result.data["PretendPersonCreate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["PretendPersonCreate"]["object"]
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None, "is_default": False}
        assert attributes["height"] == {
            "value": 167,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["weight"] == {
            "value": 85,
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["eye_color"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["description"] == {
            "value": "profile-one description",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["nothing"] == {
            "value": "profile-one nothing",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["size"] == {
            "value": "bigger human",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["shape"] == {
            "value": "bipedal",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["is_alive"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["lifespan"] == {
            "value": 85,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        assert attributes["generic_nothing"] == {
            "value": "profile-one generic nothing",
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }

        retrieved_person = await NodeManager.get_one(db=db, id=new_person_id, include_metadata=MetadataOptions.SOURCE)
        assert retrieved_person.name.value == "Apollo"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 167
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source_id == person_profile_1.id
        assert retrieved_person.height.is_default is False
        assert retrieved_person.weight.value == 85
        assert retrieved_person.weight.is_from_profile is False
        assert retrieved_person.weight.source_id is None
        assert retrieved_person.weight.is_default is False
        assert retrieved_person.eye_color.value is None
        assert retrieved_person.eye_color.is_from_profile is False
        assert retrieved_person.eye_color.source_id is None
        assert retrieved_person.eye_color.is_default is True
        assert retrieved_person.description.value == "profile-one description"
        assert retrieved_person.description.is_from_profile is True
        assert retrieved_person.description.source_id == person_profile_1.id
        assert retrieved_person.description.is_default is False
        assert retrieved_person.nothing.value == "profile-one nothing"
        assert retrieved_person.nothing.is_from_profile is True
        assert retrieved_person.nothing.source_id == person_profile_1.id
        assert retrieved_person.nothing.is_default is False
        assert retrieved_person.size.value == "bigger human"
        assert retrieved_person.size.is_from_profile is False
        assert retrieved_person.size.source_id is None
        assert retrieved_person.size.is_default is False
        assert retrieved_person.shape.value == "bipedal"
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source_id is None
        assert retrieved_person.shape.is_default is False
        assert retrieved_person.is_alive.value is None
        assert retrieved_person.is_alive.is_from_profile is False
        assert retrieved_person.is_alive.source_id is None
        assert retrieved_person.is_alive.is_default is True
        assert retrieved_person.lifespan.value == 85
        assert retrieved_person.lifespan.is_from_profile is True
        assert retrieved_person.lifespan.source_id == person_profile_1.id
        assert retrieved_person.lifespan.is_default is False
        assert retrieved_person.generic_nothing.value == "profile-one generic nothing"
        assert retrieved_person.generic_nothing.is_from_profile is True
        assert retrieved_person.generic_nothing.source_id == person_profile_1.id
        assert retrieved_person.generic_nothing.is_default is False

    async def test_step_04_update_non_profile_attribute(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PERSON_UPDATE_QUERY,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "update_data": {"id": person_1.id, "name": {"value": "Kara Thrace"}, "shape": {"value": "bipedal"}}
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["PretendPersonUpdate"]["ok"] is True
        profiles = result.data["PretendPersonUpdate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["PretendPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {
            "value": "Kara Thrace",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["shape"] == {
            "value": "bipedal",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["height"] == {
            "value": 167,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id, include_metadata=MetadataOptions.SOURCE)
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.shape.value == "bipedal"
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source_id is None
        assert retrieved_person.shape.is_default is False
        assert retrieved_person.height.value == 167
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source_id == person_profile_1.id
        assert retrieved_person.height.is_default is False

    async def test_step_05_add_profile_with_person(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_1,
        client: InfrahubClient,
    ) -> None:
        profile = await client.create(
            kind="ProfilePretendPerson",
            profile_name="profile-two",
            profile_priority=5,
            height=156,
            shape="regular",
            size="average",
            related_nodes=[person_1.id],
        )
        await profile.save()

    async def test_step_06_get_person_multiple_profiles(
        self, person_1, person_profile_1, client: InfrahubClient
    ) -> None:
        person_profile_2 = await client.get(kind="ProfilePretendPerson", profile_name__value="profile-two")
        retrieved_person = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        await retrieved_person.profiles.fetch()

        assert set(retrieved_person.profiles.peer_ids) == {person_profile_1.id, person_profile_2.id}
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 156
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source.id == person_profile_2.id
        assert retrieved_person.height.is_default is False
        assert retrieved_person.weight.value == 70
        assert retrieved_person.weight.is_from_profile is False
        assert retrieved_person.weight.source is None
        assert retrieved_person.weight.is_default is False
        assert retrieved_person.eye_color.value is None
        assert retrieved_person.eye_color.is_from_profile is False
        assert retrieved_person.eye_color.source is None
        assert retrieved_person.eye_color.is_default is True
        assert retrieved_person.description.value == "profile-one description"
        assert retrieved_person.description.is_from_profile is True
        assert retrieved_person.description.source.id == person_profile_1.id
        assert retrieved_person.description.is_default is False
        assert retrieved_person.nothing.value == "profile-one nothing"
        assert retrieved_person.nothing.is_from_profile is True
        assert retrieved_person.nothing.source.id == person_profile_1.id
        assert retrieved_person.nothing.is_default is False
        assert retrieved_person.shape.value == "bipedal"
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source is None
        assert retrieved_person.shape.is_default is False
        assert retrieved_person.size.value == "human"
        assert retrieved_person.size.is_from_profile is False
        assert retrieved_person.size.source is None
        assert retrieved_person.size.is_default is False

    async def test_step_07_update_person_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client,
    ) -> None:
        person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PERSON_UPDATE_QUERY,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"update_data": {"id": person_2.id, "profiles": []}},
        )

        assert result.errors is None
        assert result.data
        assert result.data["PretendPersonUpdate"]["ok"] is True
        profiles = result.data["PretendPersonUpdate"]["object"]["profiles"]["edges"]
        assert profiles == []
        attributes = result.data["PretendPersonUpdate"]["object"]
        assert attributes["id"] == person_2.id
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None, "is_default": False}
        assert attributes["height"] == {"value": None, "is_from_profile": False, "source": None, "is_default": True}
        assert attributes["description"] == {
            "value": "placeholder",
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["nothing"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["shape"] == {
            "value": "bipedal",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["size"] == {
            "value": "bigger human",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["lifespan"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }
        assert attributes["generic_nothing"] == {
            "value": None,
            "is_from_profile": False,
            "source": None,
            "is_default": True,
        }

        retrieved_person = await NodeManager.get_one(db=db, id=person_2.id, include_metadata=MetadataOptions.SOURCE)
        assert retrieved_person.name.value == "Apollo"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value is None
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source_id is None
        assert retrieved_person.height.is_default is True
        assert retrieved_person.shape.value == "bipedal"
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source_id is None
        assert retrieved_person.shape.is_default is False
        assert retrieved_person.size.value == "bigger human"
        assert retrieved_person.size.is_from_profile is False
        assert retrieved_person.size.source_id is None
        assert retrieved_person.size.is_default is False
        assert retrieved_person.description.value == "placeholder"
        assert retrieved_person.description.is_from_profile is False
        assert retrieved_person.description.source_id is None
        assert retrieved_person.description.is_default is True
        assert retrieved_person.nothing.value is None
        assert retrieved_person.nothing.is_from_profile is False
        assert retrieved_person.nothing.source_id is None
        assert retrieved_person.nothing.is_default is True
        assert retrieved_person.lifespan.value is None
        assert retrieved_person.lifespan.is_from_profile is False
        assert retrieved_person.lifespan.source_id is None
        assert retrieved_person.lifespan.is_default is True
        assert retrieved_person.generic_nothing.value is None
        assert retrieved_person.generic_nothing.is_from_profile is False
        assert retrieved_person.generic_nothing.source_id is None
        assert retrieved_person.generic_nothing.is_default is True

    async def test_step_08_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
    ) -> None:
        person_profile_2 = await client.get(kind="ProfilePretendPerson", profile_name__value="profile-two")
        await person_profile_2.delete()

    async def test_step_09_check_persons(
        self, db: InfrahubDatabase, person_1, person_profile_1, client: InfrahubClient, default_branch: Branch
    ) -> None:
        retrieved_person_1 = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.height.value == 167
        assert retrieved_person_1.height.is_from_profile is True
        assert retrieved_person_1.height.source.id == person_profile_1.id
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_1.weight.value == 70
        assert retrieved_person_1.weight.is_from_profile is False
        assert retrieved_person_1.weight.source is None
        assert retrieved_person_1.weight.is_default is False
        assert retrieved_person_1.eye_color.value is None
        assert retrieved_person_1.eye_color.is_from_profile is False
        assert retrieved_person_1.eye_color.source is None
        assert retrieved_person_1.eye_color.is_default is True
        assert retrieved_person_1.description.value == "profile-one description"
        assert retrieved_person_1.description.is_from_profile is True
        assert retrieved_person_1.description.source.id == person_profile_1.id
        assert retrieved_person_1.description.is_default is False
        assert retrieved_person_1.nothing.value == "profile-one nothing"
        assert retrieved_person_1.nothing.is_from_profile is True
        assert retrieved_person_1.nothing.source.id == person_profile_1.id
        assert retrieved_person_1.nothing.is_default is False
        assert retrieved_person_1.size.value == "human"
        assert retrieved_person_1.size.is_from_profile is False
        assert retrieved_person_1.size.source is None
        assert retrieved_person_1.size.is_default is False
        assert retrieved_person_1.shape.value == "bipedal"
        assert retrieved_person_1.shape.is_from_profile is False
        assert retrieved_person_1.shape.source is None
        assert retrieved_person_1.shape.is_default is False

        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None
        assert retrieved_person_2.height.is_default is True
        assert retrieved_person_2.weight.value == 85
        assert retrieved_person_2.weight.is_from_profile is False
        assert retrieved_person_2.weight.source is None
        assert retrieved_person_2.weight.is_default is False
        assert retrieved_person_2.eye_color.value is None
        assert retrieved_person_2.eye_color.is_from_profile is False
        assert retrieved_person_2.eye_color.source is None
        assert retrieved_person_2.eye_color.is_default is True
        assert retrieved_person_2.description.value == "placeholder"
        assert retrieved_person_2.description.is_from_profile is False
        assert retrieved_person_2.description.source is None
        assert retrieved_person_2.description.is_default is True
        assert retrieved_person_2.nothing.value is None
        assert retrieved_person_2.nothing.is_from_profile is False
        assert retrieved_person_2.nothing.source is None
        assert retrieved_person_2.nothing.is_default is True
        assert retrieved_person_2.size.value == "bigger human"
        assert retrieved_person_2.size.is_from_profile is False
        assert retrieved_person_2.size.source is None
        assert retrieved_person_2.size.is_default is False
        assert retrieved_person_2.shape.value == "bipedal"
        assert retrieved_person_2.shape.is_from_profile is False
        assert retrieved_person_2.shape.source is None
        assert retrieved_person_2.shape.is_default is False

    async def test_step_10_update_person_override_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PERSON_UPDATE_QUERY,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "update_data": {
                    "id": person_1.id,
                    "height": {"value": 145},
                    "shape": {"value": "symmetrical bilateral"},
                }
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["PretendPersonUpdate"]["ok"] is True
        profiles = result.data["PretendPersonUpdate"]["object"]["profiles"]["edges"]
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["PretendPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {
            "value": "Kara Thrace",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["height"] == {"value": 145, "is_from_profile": False, "source": None, "is_default": False}
        assert attributes["shape"] == {
            "value": "symmetrical bilateral",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }

        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id)
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 145
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source_id is None
        assert retrieved_person.height.is_default is False
        assert retrieved_person.shape.value == "symmetrical bilateral"
        assert retrieved_person.shape.is_from_profile is False
        assert retrieved_person.shape.source_id is None
        assert retrieved_person.shape.is_default is False

    async def test_step_11_update_existing_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_profile_1,
        person_1,
        client: InfrahubClient,
    ) -> None:
        person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        person_profile_1.profile_priority.value = 11
        person_profile_1.height.value = 134
        person_profile_1.nothing.value = "profile-one nothing updated"
        person_profile_1.generic_nothing.value = "profile-one generic nothing updated"
        await person_profile_1.save()

        updated_person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        assert updated_person_profile_1.profile_name.value == "profile-one"
        assert updated_person_profile_1.profile_priority.value == 11
        assert updated_person_profile_1.height.value == 134
        assert updated_person_profile_1.nothing.value == "profile-one nothing updated"
        assert updated_person_profile_1.generic_nothing.value == "profile-one generic nothing updated"
        await updated_person_profile_1.related_nodes.fetch()

        assert len(updated_person_profile_1.related_nodes.peers) == 1
        assert updated_person_profile_1.related_nodes.peers[0].id == person_1.id

    async def test_step_12_check_persons_again(
        self, db: InfrahubDatabase, default_branch: Branch, person_1, person_profile_1, client: InfrahubClient
    ) -> None:
        retrieved_person_1 = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_1.nothing.value == "profile-one nothing updated"
        assert retrieved_person_1.nothing.is_from_profile is True
        assert retrieved_person_1.nothing.source.id == person_profile_1.id
        assert retrieved_person_1.nothing.is_default is False
        assert retrieved_person_1.generic_nothing.value == "profile-one generic nothing updated"
        assert retrieved_person_1.generic_nothing.is_from_profile is True
        assert retrieved_person_1.generic_nothing.source.id == person_profile_1.id
        assert retrieved_person_1.generic_nothing.is_default is False

        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None
        assert retrieved_person_2.height.is_default is True
        assert retrieved_person_2.nothing.value is None
        assert retrieved_person_2.nothing.is_from_profile is False
        assert retrieved_person_2.nothing.source is None
        assert retrieved_person_2.nothing.is_default is True
        assert retrieved_person_2.generic_nothing.value is None
        assert retrieved_person_2.generic_nothing.is_from_profile is False
        assert retrieved_person_2.generic_nothing.source is None
        assert retrieved_person_2.generic_nothing.is_default is True

    async def test_step_13_update_existing_profile_related_nodes(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_profile_1,
        person_1,
        client: InfrahubClient,
    ) -> None:
        person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)
        person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        await person_profile_1.related_nodes.fetch()
        person_profile_1.related_nodes.remove(person_1.id)
        person_profile_1.related_nodes.add(person_2)
        await person_profile_1.save()

        updated_person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        assert updated_person_profile_1.profile_name.value == "profile-one"
        await updated_person_profile_1.related_nodes.fetch()
        assert len(updated_person_profile_1.related_nodes.peers) == 1
        assert updated_person_profile_1.related_nodes.peers[0].id == person_2.id

    async def test_step_14_check_persons_again(
        self, default_branch: Branch, person_1, person_profile_1, client: InfrahubClient
    ) -> None:
        retrieved_person_1 = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        retrieved_person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)

        await retrieved_person_1.profiles.fetch()
        assert retrieved_person_1.profiles.peer_ids == []
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.weight.value == 70
        assert retrieved_person_1.weight.is_from_profile is False
        assert retrieved_person_1.weight.source is None
        assert retrieved_person_1.weight.is_default is False
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_1.eye_color.value is None
        assert retrieved_person_1.eye_color.is_from_profile is False
        assert retrieved_person_1.eye_color.source is None
        assert retrieved_person_1.eye_color.is_default is True
        assert retrieved_person_1.description.value == "placeholder"
        assert retrieved_person_1.description.is_from_profile is False
        assert retrieved_person_1.description.source is None
        assert retrieved_person_1.description.is_default is True
        assert retrieved_person_1.nothing.value is None
        assert retrieved_person_1.nothing.is_from_profile is False
        assert retrieved_person_1.nothing.source is None
        assert retrieved_person_1.nothing.is_default is True
        assert retrieved_person_1.size.value == "human"
        assert retrieved_person_1.size.is_from_profile is False
        assert retrieved_person_1.size.source is None
        assert retrieved_person_1.size.is_default is False
        assert retrieved_person_1.shape.value == "symmetrical bilateral"
        assert retrieved_person_1.shape.is_from_profile is False
        assert retrieved_person_1.shape.source is None
        assert retrieved_person_1.shape.is_default is False
        assert retrieved_person_1.is_alive.value is None
        assert retrieved_person_1.is_alive.is_from_profile is False
        assert retrieved_person_1.is_alive.source is None
        assert retrieved_person_1.is_alive.is_default is True
        assert retrieved_person_1.lifespan.value is None
        assert retrieved_person_1.lifespan.is_from_profile is False
        assert retrieved_person_1.lifespan.source is None
        assert retrieved_person_1.lifespan.is_default is True
        assert retrieved_person_1.generic_nothing.value is None
        assert retrieved_person_1.generic_nothing.is_from_profile is False
        assert retrieved_person_1.generic_nothing.source is None
        assert retrieved_person_1.generic_nothing.is_default is True

        await retrieved_person_2.profiles.fetch()
        assert retrieved_person_2.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.weight.value == 85
        assert retrieved_person_2.weight.is_from_profile is False
        assert retrieved_person_2.weight.source is None
        assert retrieved_person_2.weight.is_default is False
        assert retrieved_person_2.height.value == 134
        assert retrieved_person_2.height.is_from_profile is True
        assert retrieved_person_2.height.source.id == person_profile_1.id
        assert retrieved_person_2.height.is_default is False
        assert retrieved_person_2.eye_color.value is None
        assert retrieved_person_2.eye_color.is_from_profile is False
        assert retrieved_person_2.eye_color.source is None
        assert retrieved_person_2.eye_color.is_default is True
        assert retrieved_person_2.description.value == "profile-one description"
        assert retrieved_person_2.description.is_from_profile is True
        assert retrieved_person_2.description.source.id == person_profile_1.id
        assert retrieved_person_2.description.is_default is False
        assert retrieved_person_2.nothing.value == "profile-one nothing updated"
        assert retrieved_person_2.nothing.is_from_profile is True
        assert retrieved_person_2.nothing.source.id == person_profile_1.id
        assert retrieved_person_2.nothing.is_default is False
        assert retrieved_person_2.size.value == "bigger human"
        assert retrieved_person_2.size.is_from_profile is False
        assert retrieved_person_2.size.source is None
        assert retrieved_person_2.size.is_default is False
        assert retrieved_person_2.shape.value == "bipedal"
        assert retrieved_person_2.shape.is_from_profile is False
        assert retrieved_person_2.shape.source is None
        assert retrieved_person_2.shape.is_default is False
        assert retrieved_person_2.is_alive.value is None
        assert retrieved_person_2.is_alive.is_from_profile is False
        assert retrieved_person_2.is_alive.source is None
        assert retrieved_person_2.is_alive.is_default is True
        assert retrieved_person_2.lifespan.value == 85
        assert retrieved_person_2.lifespan.is_from_profile is True
        assert retrieved_person_2.lifespan.source.id == person_profile_1.id
        assert retrieved_person_2.lifespan.is_default is False
        assert retrieved_person_2.generic_nothing.value == "profile-one generic nothing updated"
        assert retrieved_person_2.generic_nothing.is_from_profile is True
        assert retrieved_person_2.generic_nothing.source.id == person_profile_1.id
        assert retrieved_person_2.generic_nothing.is_default is False

    async def test_step_15_schema_update_add_attributes(
        self,
        default_branch,
        person_profile_1: Node,
        lifeform_profile_1: Node,
        schema_root_02,
        client: InfrahubClient,
    ) -> None:
        updated_person_profile_schema = await client.schema.get(
            kind="ProfilePretendPerson", branch=default_branch.name, refresh=True
        )
        assert set(updated_person_profile_schema.attribute_names) == {
            "age",
            "description",
            "eye_color",
            "generic_nothing",
            "height",
            "is_alive",
            "lifespan",
            "nothing",
            "profile_name",
            "profile_priority",
            "shape",
            "size",
            "value",
            "weight",
        }
        updated_lifeform_profile_schema = await client.schema.get(
            kind="ProfilePretendLifeform", branch=default_branch.name, refresh=True
        )
        assert set(updated_lifeform_profile_schema.attribute_names) == {
            "size",
            "shape",
            "is_alive",
            "lifespan",
            "generic_nothing",
            "profile_name",
            "profile_priority",
            "value",
        }

        updated_person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        assert updated_person_profile_1.height.value == 134
        assert updated_person_profile_1.description.value == "profile-one description"
        assert updated_person_profile_1.nothing.value == "profile-one nothing updated"
        assert updated_person_profile_1.age.value is None
        assert updated_person_profile_1.weight.value is None
        assert updated_person_profile_1.eye_color.value is None
        assert updated_person_profile_1.size.value is None
        assert updated_person_profile_1.is_alive.value is None
        assert updated_person_profile_1.value.value is None
        with pytest.raises(AttributeError):
            _ = updated_person_profile_1.not_for_profiles
        with pytest.raises(AttributeError):
            _ = updated_person_profile_1.generic_not_for_profiles

        updated_lifeform_profile_1 = await client.get(kind="ProfilePretendLifeform", id=lifeform_profile_1.id)
        assert updated_lifeform_profile_1.size.value is None
        assert updated_lifeform_profile_1.shape.value == "lifeform-profile-one shape"
        assert updated_lifeform_profile_1.is_alive.value is None
        assert updated_lifeform_profile_1.lifespan.value is None
        assert updated_lifeform_profile_1.generic_nothing.value == "lifeform-profile-one generic nothing"
        assert updated_lifeform_profile_1.value.value is None
        with pytest.raises(AttributeError):
            _ = updated_lifeform_profile_1.generic_not_for_profiles

    async def test_step_16_update_profile_with_new_attribute(
        self,
        default_branch,
        person_profile_1: Node,
        lifeform_profile_1: Node,
        client: InfrahubClient,
    ) -> None:
        updated_person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        updated_person_profile_1.age.value = 25
        updated_person_profile_1.eye_color.value = "blurple"
        updated_person_profile_1.value.value = 42
        updated_person_profile_1.is_alive.value = True
        await updated_person_profile_1.save()

        updated_lifeform_profile_1 = await client.get(kind="ProfilePretendLifeform", id=lifeform_profile_1.id)
        updated_lifeform_profile_1.size.value = "lifeform-profile-big"
        updated_lifeform_profile_1.value.value = 84
        await updated_lifeform_profile_1.save()

    async def test_step_17_use_generic_profile(
        self,
        client: InfrahubClient,
        person_profile_1: Node,
        lifeform_profile_1: Node,
    ) -> None:
        person_two = await client.get(kind="PretendPerson", name__value="Apollo")
        await person_two.profiles.fetch()
        person_two.profiles.add(lifeform_profile_1.id)
        await person_two.save()

    async def test_step_17_check_persons_again(
        self, default_branch: Branch, person_1, person_profile_1: Node, lifeform_profile_1: Node, client: InfrahubClient
    ) -> None:
        retrieved_person_1 = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        retrieved_person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)

        await retrieved_person_1.profiles.fetch()
        assert retrieved_person_1.profiles.peer_ids == []
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_1.weight.value == 70
        assert retrieved_person_1.weight.is_from_profile is False
        assert retrieved_person_1.weight.source is None
        assert retrieved_person_1.weight.is_default is False
        assert retrieved_person_1.eye_color.value is None
        assert retrieved_person_1.eye_color.is_from_profile is False
        assert retrieved_person_1.eye_color.source is None
        assert retrieved_person_1.eye_color.is_default is True
        assert retrieved_person_1.description.value == "placeholder"
        assert retrieved_person_1.description.is_from_profile is False
        assert retrieved_person_1.description.source is None
        assert retrieved_person_1.description.is_default is True
        assert retrieved_person_1.nothing.value is None
        assert retrieved_person_1.nothing.is_from_profile is False
        assert retrieved_person_1.nothing.source is None
        assert retrieved_person_1.nothing.is_default is True
        assert retrieved_person_1.age.value is None
        assert retrieved_person_1.age.is_from_profile is False
        assert retrieved_person_1.age.source is None
        assert retrieved_person_1.age.is_default is True
        assert retrieved_person_1.size.value == "human"
        assert retrieved_person_1.size.is_from_profile is False
        assert retrieved_person_1.size.source is None
        assert retrieved_person_1.size.is_default is False
        assert retrieved_person_1.shape.value == "symmetrical bilateral"
        assert retrieved_person_1.shape.is_from_profile is False
        assert retrieved_person_1.shape.source is None
        assert retrieved_person_1.shape.is_default is False
        assert retrieved_person_1.is_alive.value is None
        assert retrieved_person_1.is_alive.is_from_profile is False
        assert retrieved_person_1.is_alive.source is None
        assert retrieved_person_1.is_alive.is_default is True
        assert retrieved_person_1.lifespan.value is None
        assert retrieved_person_1.lifespan.is_from_profile is False
        assert retrieved_person_1.lifespan.source is None
        assert retrieved_person_1.lifespan.is_default is True
        assert retrieved_person_1.generic_nothing.value is None
        assert retrieved_person_1.generic_nothing.is_from_profile is False
        assert retrieved_person_1.generic_nothing.source is None
        assert retrieved_person_1.generic_nothing.is_default is True
        assert retrieved_person_1.value.value is None
        assert retrieved_person_1.value.is_from_profile is False
        assert retrieved_person_1.value.source is None
        assert retrieved_person_1.value.is_default is True

        await retrieved_person_2.profiles.fetch()
        assert set(retrieved_person_2.profiles.peer_ids) == {person_profile_1.id, lifeform_profile_1.id}
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value == 134
        assert retrieved_person_2.height.is_from_profile is True
        assert retrieved_person_2.height.source.id == person_profile_1.id
        assert retrieved_person_2.height.is_default is False
        assert retrieved_person_2.weight.value == 85
        assert retrieved_person_2.weight.is_from_profile is False
        assert retrieved_person_2.weight.source is None
        assert retrieved_person_2.weight.is_default is False
        assert retrieved_person_2.eye_color.value == "blurple"
        assert retrieved_person_2.eye_color.is_from_profile is True
        assert retrieved_person_2.eye_color.source.id == person_profile_1.id
        assert retrieved_person_2.eye_color.is_default is False
        assert retrieved_person_2.description.value == "profile-one description"
        assert retrieved_person_2.description.is_from_profile is True
        assert retrieved_person_2.description.source.id == person_profile_1.id
        assert retrieved_person_2.description.is_default is False
        assert retrieved_person_2.nothing.value == "profile-one nothing updated"
        assert retrieved_person_2.nothing.is_from_profile is True
        assert retrieved_person_2.nothing.source.id == person_profile_1.id
        assert retrieved_person_2.nothing.is_default is False
        assert retrieved_person_2.age.value == 25
        assert retrieved_person_2.age.is_from_profile is True
        assert retrieved_person_2.age.source.id == person_profile_1.id
        assert retrieved_person_2.age.is_default is False
        assert retrieved_person_2.size.value == "bigger human"
        assert retrieved_person_2.size.is_from_profile is False
        assert retrieved_person_2.size.source is None
        assert retrieved_person_2.size.is_default is False
        assert retrieved_person_2.shape.value == "bipedal"
        assert retrieved_person_2.shape.is_from_profile is False
        assert retrieved_person_2.shape.source is None
        assert retrieved_person_2.shape.is_default is False
        assert retrieved_person_2.is_alive.value is True
        assert retrieved_person_2.is_alive.is_from_profile is True
        assert retrieved_person_2.is_alive.source.id == person_profile_1.id
        assert retrieved_person_2.is_alive.is_default is False
        assert retrieved_person_2.lifespan.value == 85
        assert retrieved_person_2.lifespan.is_from_profile is True
        assert retrieved_person_2.lifespan.source.id == person_profile_1.id
        assert retrieved_person_2.lifespan.is_default is False
        assert retrieved_person_2.generic_nothing.value == "lifeform-profile-one generic nothing"
        assert retrieved_person_2.generic_nothing.is_from_profile is True
        assert retrieved_person_2.generic_nothing.source.id == lifeform_profile_1.id
        assert retrieved_person_2.generic_nothing.is_default is False
        assert retrieved_person_2.value.value == 84
        assert retrieved_person_2.value.is_from_profile is True
        assert retrieved_person_2.value.source.id == lifeform_profile_1.id
        assert retrieved_person_2.value.is_default is False

    async def test_step_18_check_profile_for_removed_attribute(
        self,
        db: InfrahubDatabase,
        schema_root_03,
        default_branch,
        person_profile_1,
        lifeform_profile_1,
        client: InfrahubClient,
    ) -> None:
        updated_schema = await client.schema.get(kind="ProfilePretendPerson", branch=default_branch.name, refresh=True)
        assert set(updated_schema.attribute_names) == {
            "age",
            "eye_color",
            "is_alive",
            "profile_name",
            "profile_priority",
            "size",
            "value",
            "weight",
        }
        updated_lifeform_profile_schema = await client.schema.get(
            kind="ProfilePretendLifeform", branch=default_branch.name, refresh=True
        )
        assert set(updated_lifeform_profile_schema.attribute_names) == {
            "size",
            "is_alive",
            "profile_name",
            "profile_priority",
            "value",
        }

        person_profile_1 = await client.get(kind="ProfilePretendPerson", id=person_profile_1.id)
        assert person_profile_1.age.value == 25
        assert person_profile_1.eye_color.value == "blurple"
        assert person_profile_1.is_alive.value is True
        assert person_profile_1.size.value is None
        assert person_profile_1.value.value == 42
        assert person_profile_1.weight.value is None

        with pytest.raises(AttributeError):
            _ = person_profile_1.height
        with pytest.raises(AttributeError):
            _ = person_profile_1.description
        with pytest.raises(AttributeError):
            _ = person_profile_1.nothing
        with pytest.raises(AttributeError):
            _ = person_profile_1.shape
        with pytest.raises(AttributeError):
            _ = person_profile_1.lifespan
        with pytest.raises(AttributeError):
            _ = person_profile_1.generic_nothing

        lifeform_profile_1 = await client.get(kind="ProfilePretendLifeform", id=lifeform_profile_1.id)
        assert lifeform_profile_1.size.value == "lifeform-profile-big"
        assert lifeform_profile_1.is_alive.value is None
        assert lifeform_profile_1.value.value == 84

        with pytest.raises(AttributeError):
            _ = lifeform_profile_1.shape
        with pytest.raises(AttributeError):
            _ = lifeform_profile_1.lifespan
        with pytest.raises(AttributeError):
            _ = lifeform_profile_1.generic_nothing

    async def test_step_19_check_persons_again(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
        lifeform_profile_1,
        client: InfrahubClient,
    ) -> None:
        await client.schema.get(kind="PretendPerson", branch=default_branch.name, refresh=True)
        retrieved_person_1 = await client.get(kind="PretendPerson", id=person_1.id, property=True)
        retrieved_person_2 = await client.get(kind="PretendPerson", name__value="Apollo", property=True)

        await retrieved_person_1.profiles.fetch()
        assert retrieved_person_1.profiles.peer_ids == []
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.age.value is None
        assert retrieved_person_1.age.is_from_profile is False
        assert retrieved_person_1.age.source is None
        assert retrieved_person_1.age.is_default is True
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_1.weight.value == 70
        assert retrieved_person_1.weight.is_from_profile is False
        assert retrieved_person_1.weight.source is None
        assert retrieved_person_1.weight.is_default is False
        assert retrieved_person_1.eye_color.value is None
        assert retrieved_person_1.eye_color.is_from_profile is False
        assert retrieved_person_1.eye_color.source is None
        assert retrieved_person_1.eye_color.is_default is True
        assert retrieved_person_1.description.value == "placeholder"
        assert retrieved_person_1.description.is_from_profile is False
        assert retrieved_person_1.description.source is None
        assert retrieved_person_1.description.is_default is True
        assert retrieved_person_1.size.value == "human"
        assert retrieved_person_1.size.is_from_profile is False
        assert retrieved_person_1.size.source is None
        assert retrieved_person_1.size.is_default is False
        assert retrieved_person_1.shape.value == "symmetrical bilateral"
        assert retrieved_person_1.shape.is_from_profile is False
        assert retrieved_person_1.shape.source is None
        assert retrieved_person_1.shape.is_default is False
        assert retrieved_person_1.is_alive.value is None
        assert retrieved_person_1.is_alive.is_from_profile is False
        assert retrieved_person_1.is_alive.source is None
        assert retrieved_person_1.is_alive.is_default is True
        assert retrieved_person_1.lifespan.value is None
        assert retrieved_person_1.lifespan.is_from_profile is False
        assert retrieved_person_1.lifespan.source is None
        assert retrieved_person_1.lifespan.is_default is True
        assert retrieved_person_1.value.value is None
        assert retrieved_person_1.value.is_from_profile is False
        assert retrieved_person_1.value.source is None
        assert retrieved_person_1.value.is_default is True
        with pytest.raises(AttributeError):
            _ = retrieved_person_1.nothing
        with pytest.raises(AttributeError):
            _ = retrieved_person_1.generic_nothing

        await retrieved_person_2.profiles.fetch()
        assert set(retrieved_person_2.profiles.peer_ids) == {person_profile_1.id, lifeform_profile_1.id}
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.age.value == 25
        assert retrieved_person_2.age.is_from_profile is True
        assert retrieved_person_2.age.source.id == person_profile_1.id
        assert retrieved_person_2.age.is_default is False
        assert retrieved_person_2.height.value == 134
        assert retrieved_person_2.height.is_from_profile is True
        assert retrieved_person_2.height.source.id == person_profile_1.id
        assert retrieved_person_2.height.is_default is False
        assert retrieved_person_2.weight.value == 85
        assert retrieved_person_2.weight.is_from_profile is False
        assert retrieved_person_2.weight.source is None
        assert retrieved_person_2.weight.is_default is False
        assert retrieved_person_2.eye_color.value == "blurple"
        assert retrieved_person_2.eye_color.is_from_profile is True
        assert retrieved_person_2.eye_color.source.id == person_profile_1.id
        assert retrieved_person_2.eye_color.is_default is False
        assert retrieved_person_2.description.value == "profile-one description"
        assert retrieved_person_2.description.is_from_profile is True
        assert retrieved_person_2.description.source.id == person_profile_1.id
        assert retrieved_person_2.description.is_default is False
        assert retrieved_person_2.size.value == "bigger human"
        assert retrieved_person_2.size.is_from_profile is False
        assert retrieved_person_2.size.source is None
        assert retrieved_person_2.size.is_default is False
        assert retrieved_person_2.shape.value == "bipedal"
        assert retrieved_person_2.shape.is_from_profile is False
        assert retrieved_person_2.shape.source is None
        assert retrieved_person_2.shape.is_default is False
        assert retrieved_person_2.is_alive.value is True
        assert retrieved_person_2.is_alive.is_from_profile is True
        assert retrieved_person_2.is_alive.source.id == person_profile_1.id
        assert retrieved_person_2.is_alive.is_default is False
        assert retrieved_person_2.lifespan.value == 85
        assert retrieved_person_2.lifespan.is_from_profile is True
        assert retrieved_person_2.lifespan.source.id == person_profile_1.id
        assert retrieved_person_2.lifespan.is_default is False
        assert retrieved_person_2.value.value == 84
        assert retrieved_person_2.value.is_from_profile is True
        assert retrieved_person_2.value.source.id == lifeform_profile_1.id
        assert retrieved_person_2.value.is_default is False
        with pytest.raises(AttributeError):
            _ = retrieved_person_2.nothing
        with pytest.raises(AttributeError):
            _ = retrieved_person_2.generic_nothing
