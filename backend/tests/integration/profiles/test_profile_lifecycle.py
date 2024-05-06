import pytest
from graphql import graphql
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
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
        retrieved_person = await client.get(kind="TestingPerson", id=person_1.id)

        assert retrieved_person.profiles.peer_ids == []
        assert retrieved_person.name.value == "Starbuck"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source is None
        assert retrieved_person.height.value is None
        assert retrieved_person.height.is_from_profile is False
        assert retrieved_person.height.source is None

    async def test_step_02_one_person_add_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_1,
        person_profile_1,
    ):
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
                        }
                        height {
                            value
                            source { id }
                            is_from_profile
                        }
                    }
                }
            }
        """ % {"person_id": person_1.id, "profile_id": person_profile_1.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
        assert attributes["name"] == {"value": "Starbuck", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": 167, "is_from_profile": True, "source": {"id": person_profile_1.id}}

    async def test_step_03_create_person_with_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_profile_1,
    ):
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
                        }
                        height {
                            value
                            source { id }
                            is_from_profile
                        }
                    }
                }
            }
        """ % {"profile_id": person_profile_1.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
        profiles = result.data["TestingPersonCreate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonCreate"]["object"]
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": 167, "is_from_profile": True, "source": {"id": person_profile_1.id}}

    async def test_step_04_update_non_profile_attribute(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_1,
        person_profile_1,
    ):
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
                        }
                        height {
                            value
                            source { id }
                            is_from_profile
                        }
                    }
                }
            }
        """ % {
            "person_id": person_1.id,
        }

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
        assert attributes["name"] == {"value": "Kara Thrace", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": 167, "is_from_profile": True, "source": {"id": person_profile_1.id}}

    async def test_step_05_add_profile_with_person(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_1,
    ):
        mutation = """
            mutation {
                ProfileTestingPersonCreate(data: {
                    profile_name: {value: "profile-two"},
                    profile_priority: {value: 5},
                    height: {value: 156}
                    related_nodes: [{id: "%(person_id)s"}]
                } ) {
                    ok
                    object {
                        related_nodes { edges { node { id } } }
                        profile_name { value }
                        profile_priority { value }
                        height { value }
                    }
                }
            }
        """ % {"person_id": person_1.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert result.errors is None
        assert result.data
        assert result.data["ProfileTestingPersonCreate"]["ok"] is True
        nodes = result.data["ProfileTestingPersonCreate"]["object"]["related_nodes"]["edges"]
        assert len(nodes) == 1
        assert nodes == [{"node": {"id": person_1.id}}]
        attributes = result.data["ProfileTestingPersonCreate"]["object"]
        assert attributes["profile_name"] == {"value": "profile-two"}
        assert attributes["profile_priority"] == {"value": 5}
        assert attributes["height"] == {"value": 156}

    async def test_step_06_get_person_multiple_profiles(self, person_1, person_profile_1, client: InfrahubClient):
        person_profile_2 = await client.get(kind="ProfileTestingPerson", profile_name__value="profile-two")
        retrieved_person = await client.get(kind="TestingPerson", id=person_1.id)
        await retrieved_person.profiles.fetch()

        assert set(retrieved_person.profiles.peer_ids) == {person_profile_1.id, person_profile_2.id}
        assert retrieved_person.name.value == "Kara Thrace"
        assert retrieved_person.name.is_from_profile is False
        assert retrieved_person.name.source is None
        assert retrieved_person.height.value == 156
        assert retrieved_person.height.is_from_profile is True
        assert retrieved_person.height.source.id == person_profile_2.id

    async def test_step_07_update_person_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
    ):
        person_2 = await client.get(kind="TestingPerson", name__value="Apollo")
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
                        }
                        height {
                            value
                            source { id }
                            is_from_profile
                        }
                    }
                }
            }
        """ % {"person_id": person_2.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
        assert attributes["name"] == {"value": "Apollo", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": None, "is_from_profile": False, "source": None}

    async def test_step_08_delete_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
    ):
        person_profile_2 = await client.get(kind="ProfileTestingPerson", profile_name__value="profile-two")
        mutation = """
            mutation {
                ProfileTestingPersonDelete(data: {id: "%(profile_id)s"}) {
                    ok
                }
            }
        """ % {"profile_id": person_profile_2.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert not result.errors
        assert result.data
        assert result.data["ProfileTestingPersonDelete"]["ok"] is True

    async def test_step_09_check_persons(
        self, db: InfrahubDatabase, person_1, person_profile_1, client: InfrahubClient
    ):
        retrieved_person_1 = await client.get(kind="TestingPerson", id=person_1.id)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="TestingPerson", name__value="Apollo")

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.height.value == 167
        assert retrieved_person_1.height.is_from_profile is True
        assert retrieved_person_1.height.source.id == person_profile_1.id
        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None

    async def test_step_10_update_person_override_profile(
        self,
        db: InfrahubDatabase,
        default_branch,
        person_1,
        person_profile_1,
    ):
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
                        }
                        height {
                            value
                            source { id }
                            is_from_profile
                        }
                    }
                }
            }
        """ % {"person_id": person_1.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
        assert attributes["name"] == {"value": "Kara Thrace", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": 145, "is_from_profile": False, "source": None}

    async def test_step_11_add_profile_with_person(
        self, db: InfrahubDatabase, default_branch, person_profile_1, person_1
    ):
        mutation = """
            mutation {
                ProfileTestingPersonUpdate(data: {
                    id: "%(profile_id)s"
                    profile_priority: {value: 11},
                    height: {value: 134}
                } ) {
                    ok
                    object {
                        related_nodes { edges { node { id } } }
                        profile_name { value }
                        profile_priority { value }
                        height { value }
                    }
                }
            }
        """ % {"profile_id": person_profile_1.id}

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=mutation,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert result.errors is None
        assert result.data
        assert result.data["ProfileTestingPersonUpdate"]["ok"] is True
        nodes = result.data["ProfileTestingPersonUpdate"]["object"]["related_nodes"]["edges"]
        assert len(nodes) == 1
        assert nodes == [{"node": {"id": person_1.id}}]
        attributes = result.data["ProfileTestingPersonUpdate"]["object"]
        assert attributes["profile_name"] == {"value": "profile-one"}
        assert attributes["profile_priority"] == {"value": 11}
        assert attributes["height"] == {"value": 134}

    async def test_step_12_check_persons_again(self, person_1, person_profile_1, client: InfrahubClient):
        retrieved_person_1 = await client.get(kind="TestingPerson", id=person_1.id)
        await retrieved_person_1.profiles.fetch()
        retrieved_person_2 = await client.get(kind="TestingPerson", name__value="Apollo")

        assert retrieved_person_1.profiles.peer_ids == [person_profile_1.id]
        assert retrieved_person_1.name.value == "Kara Thrace"
        assert retrieved_person_1.name.is_from_profile is False
        assert retrieved_person_1.name.source is None
        assert retrieved_person_1.height.value == 145
        assert retrieved_person_1.height.is_from_profile is False
        assert retrieved_person_1.height.source is None
        assert retrieved_person_2.profiles.peer_ids == []
        assert retrieved_person_2.name.value == "Apollo"
        assert retrieved_person_2.name.is_from_profile is False
        assert retrieved_person_2.name.source is None
        assert retrieved_person_2.height.value is None
        assert retrieved_person_2.height.is_from_profile is False
        assert retrieved_person_2.height.source is None
