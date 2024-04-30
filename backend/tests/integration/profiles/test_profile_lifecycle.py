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
        schema = registry.schema.get(name="TestingPerson", duplicate=False)
        person_1 = await Node.init(db=db, schema=schema)
        await person_1.new(db=db, name="Starbuck")
        await person_1.save(db=db)
        return person_1

    @pytest.fixture(scope="class")
    async def person_profile_1(self, db: InfrahubDatabase, schema_person_base) -> Node:
        profile_schema = registry.schema.get(name="ProfileTestingPerson", duplicate=False)
        person_profile_1 = await Node.init(db=db, schema=profile_schema)
        await person_profile_1.new(db=db, profile_name="profile-one", profile_priority=1, height=167)
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
        schema_person_base,
        person_1,
        person_profile_1,
        client: InfrahubClient,
    ):
        mutation = """
            mutation {
                TestingPersonUpdate(data: {id: "%(person_id)s", profiles: [{ id: "%(profile_id)s"}]}) {
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
        assert result.data["TestingPersonUpdate"]["ok"] is True
        profiles = result.data["TestingPersonUpdate"]["object"]["profiles"]["edges"]
        assert len(profiles) == 1
        assert profiles == [{"node": {"id": person_profile_1.id}}]
        attributes = result.data["TestingPersonUpdate"]["object"]
        assert attributes["id"] == person_1.id
        assert attributes["name"] == {"value": "Starbuck", "is_from_profile": False, "source": None}
        assert attributes["height"] == {"value": 167, "is_from_profile": True, "source": {"id": person_profile_1.id}}
