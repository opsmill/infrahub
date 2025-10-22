import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp


class TestProfileLifecycle(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def schema_person_base(self, db: InfrahubDatabase, initialize_registry) -> None:
        person_schema = NodeSchema(
            name="Person",
            namespace="Testing",
            include_in_menu=True,
            label="Person",
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(name="height", kind="Number", optional=True),
            ],
        )
        await load_schema(db=db, schema=SchemaRoot(version="1.0", nodes=[person_schema]))

    @pytest.fixture(scope="class")
    async def person_1(self, db: InfrahubDatabase, schema_person_base) -> Node:
        schema = registry.schema.get_node_schema(name="TestingPerson", duplicate=False)
        person_1 = await Node.init(db=db, schema=schema)
        await person_1.new(db=db, name="Starbuck")
        await person_1.save(db=db)
        return person_1

    @pytest.fixture(scope="class")
    async def person_profile_1(self, db: InfrahubDatabase, schema_person_base) -> Node:
        person_profile_1 = await Node.init(db=db, schema="ProfileTestingPerson")
        await person_profile_1.new(db=db, profile_name="profile-one", profile_priority=10, height=167)
        await person_profile_1.save(db=db)
        return person_profile_1

    async def test_step_01_one_person_no_profile(
        self, db: InfrahubDatabase, schema_person_base, person_1, person_profile_1, client: InfrahubClient
    ):
        retrieved_person = await client.get(kind="TestingPerson", id=person_1.id, property=True)

        assert retrieved_person.profiles.peer_ids == []
        assert retrieved_person.name.value == "Starbuck"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value is None
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source is None
        assert retrieved_person.height.is_default is True

    async def test_step_02_one_person_add_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        mutation = """
            mutation {
                TestingPersonUpdate(data: {id: "%(person_id)s", profiles: [{ id: "%(profile_id)s"}]}) {
                    ok
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
                    }
                }
            }
        """ % {"person_id": person_1.id, "profile_id": person_profile_1.id}

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
        assert result.data["TestingPersonUpdate"]["ok"] is True
        profiles = result.data["TestingPersonUpdate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonUpdate"]["object"]
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
        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id, include_source=True)
        assert retrieved_person.name.value == "Starbuck"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 167
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source_id == person_profile_1.id
        assert retrieved_person.height.is_default is False

    async def test_step_03_create_person_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_profile_1,
    ) -> None:
        mutation = """
            mutation {
                TestingPersonCreate(data: {name: {value: "Apollo"}, profiles: [{ id: "%(profile_id)s"}]}) {
                    ok
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
                    }
                }
            }
        """ % {"profile_id": person_profile_1.id}

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
        assert result.data["TestingPersonCreate"]["ok"] is True
        new_person_id = result.data["TestingPersonCreate"]["object"]["id"]
        profiles = result.data["TestingPersonCreate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonCreate"]["object"]
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None, "is_default": False}
        assert attributes["height"] == {
            "value": 167,
            "is_from_profile": True,
            "source": {"id": person_profile_1.id},
            "is_default": False,
        }
        retrieved_person = await NodeManager.get_one(db=db, id=new_person_id, include_source=True)
        assert retrieved_person.name.value == "Apollo"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 167
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source_id == person_profile_1.id
        assert retrieved_person.height.is_default is False

    async def test_step_04_update_non_profile_attribute(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        mutation = """
            mutation {
                TestingPersonUpdate(data: {id: "%(person_id)s", name: {value: "Kara Thrace"}}) {
                    ok
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
                    }
                }
            }
        """ % {
            "person_id": person_1.id,
        }

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
        assert result.data["TestingPersonUpdate"]["ok"] is True
        profiles = result.data["TestingPersonUpdate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {
            "value": "Kara Thrace",
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
        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id, include_source=True)
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
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
    ):
        profile = await client.create(
            kind="ProfileTestingPerson",
            profile_name="profile-two",
            profile_priority=5,
            height=156,
            related_nodes=[person_1.id],
        )
        await profile.save()

    async def test_step_06_get_person_multiple_profiles(self, person_1, person_profile_1, client: InfrahubClient):
        person_profile_2 = await client.get(kind="ProfileTestingPerson", profile_name__value="profile-two")
        retrieved_person = await client.get(kind="TestingPerson", id=person_1.id, property=True)
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

    async def test_step_07_update_person_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client,
    ) -> None:
        person_2 = await client.get(kind="TestingPerson", name__value="Apollo", property=True)
        mutation = """
            mutation {
                TestingPersonUpdate(data: {id: "%(person_id)s", profiles: []}) {
                    ok
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
                    }
                }
            }
        """ % {"person_id": person_2.id}

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
        assert result.data["TestingPersonUpdate"]["ok"] is True
        profiles = result.data["TestingPersonUpdate"]["object"]["profiles"]["edges"]
        assert profiles == []
        attributes = result.data["TestingPersonUpdate"]["object"]
        assert attributes["id"] == person_2.id
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None, "is_default": False}
        assert attributes["height"] == {"value": None, "is_from_profile": False, "source": None, "is_default": True}

        retrieved_person = await NodeManager.get_one(db=db, id=person_2.id, include_source=True)
        assert retrieved_person.name.value == "Apollo"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value is None
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source_id is None
        assert retrieved_person.height.is_default is True

    async def test_step_08_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
    ):
        person_profile_2 = await client.get(kind="ProfileTestingPerson", profile_name__value="profile-two")
        await person_profile_2.delete()

    async def test_step_09_check_persons(
        self, db: InfrahubDatabase, person_1, person_profile_1, client: InfrahubClient, default_branch: Branch
    ):
        retrieved_person_1 = await client.get(kind="TestingPerson", id=person_1.id, property=True)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="TestingPerson", name__value="Apollo", property=True)

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.height.value == 167
        assert retrieved_person_1.height.is_from_profile is True
        assert retrieved_person_1.height.source.id == person_profile_1.id
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None
        assert retrieved_person_2.height.is_default is True

    async def test_step_10_update_person_override_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_1,
        person_profile_1,
    ) -> None:
        mutation = """
            mutation {
                TestingPersonUpdate(data: {id: "%(person_id)s", height: {value: 145}}) {
                    ok
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
                    }
                }
            }
        """ % {"person_id": person_1.id}

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
        assert result.data["TestingPersonUpdate"]["ok"] is True
        profiles = result.data["TestingPersonUpdate"]["object"]["profiles"]["edges"]
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {
            "value": "Kara Thrace",
            "is_from_profile": False,
            "source": None,
            "is_default": False,
        }
        assert attributes["height"] == {"value": 145, "is_from_profile": False, "source": None, "is_default": False}
        retrieved_person = await NodeManager.get_one(db=db, id=person_1.id)
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source_id is None
        assert retrieved_person.name.is_default is False
        assert retrieved_person.height.value == 145
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source_id is None
        assert retrieved_person.height.is_default is False

    async def test_step_11_update_existing_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_profile_1,
        person_1,
        client: InfrahubClient,
    ):
        person_profile_1 = await client.get(kind="ProfileTestingPerson", id=person_profile_1.id)
        person_profile_1.profile_priority.value = 11
        person_profile_1.height.value = 134
        await person_profile_1.save()

        updated_person_profile_1 = await client.get(kind="ProfileTestingPerson", id=person_profile_1.id)
        assert updated_person_profile_1.profile_name.value == "profile-one"
        assert updated_person_profile_1.profile_priority.value == 11
        assert updated_person_profile_1.height.value == 134
        await updated_person_profile_1.related_nodes.fetch()

        assert len(updated_person_profile_1.related_nodes.peers) == 1
        assert updated_person_profile_1.related_nodes.peers[0].id == person_1.id

    async def test_step_12_check_persons_again(
        self, db: InfrahubDatabase, default_branch: Branch, person_1, person_profile_1, client: InfrahubClient
    ):
        retrieved_person_1 = await client.get(kind="TestingPerson", id=person_1.id, property=True)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="TestingPerson", name__value="Apollo", property=True)

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.name.is_default is False
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_1.height.is_default is False
        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None
        assert retrieved_person_2.height.is_default is True

    async def test_step_13_update_existing_profile_related_nodes(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_profile_1,
        person_1,
        client: InfrahubClient,
    ):
        person_2 = await client.get(kind="TestingPerson", name__value="Apollo", property=True)
        person_profile_1 = await client.get(kind="ProfileTestingPerson", id=person_profile_1.id)
        await person_profile_1.related_nodes.fetch()
        person_profile_1.related_nodes.remove(person_1.id)
        person_profile_1.related_nodes.add(person_2)
        await person_profile_1.save()

        updated_person_profile_1 = await client.get(kind="ProfileTestingPerson", id=person_profile_1.id)
        assert updated_person_profile_1.profile_name.value == "profile-one"
        await updated_person_profile_1.related_nodes.fetch()
        assert len(updated_person_profile_1.related_nodes.peers) == 1
        assert updated_person_profile_1.related_nodes.peers[0].id == person_2.id

    async def test_step_14_check_persons_again(
        self, db: InfrahubDatabase, default_branch: Branch, person_1, person_profile_1, client: InfrahubClient
    ):
        retrieved_person_1 = await client.get(kind="TestingPerson", id=person_1.id, property=True)
        retrieved_person_2 = await client.get(kind="TestingPerson", name__value="Apollo", property=True)

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

        await retrieved_person_2.profiles.fetch()
        assert retrieved_person_2.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.name.is_default is False
        assert retrieved_person_2.height.value == 134
        assert retrieved_person_2.height.is_from_profile is True
        assert retrieved_person_2.height.source.id == person_profile_1.id
        assert retrieved_person_2.height.is_default is False
