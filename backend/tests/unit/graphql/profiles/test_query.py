import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


@pytest.fixture
def criticality_schema(default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
            {"name": "fancy", "kind": "Text", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)


async def test_create_profile_in_schema(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile = registry.schema.get("ProfileTestCriticality", branch=default_branch)

    obj1 = await Node.init(db=db, schema=profile)
    await obj1.new(db=db, profile_name="prof1", level=8)
    await obj1.save(db=db)

    query = """
    query {
        ProfileTestCriticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["ProfileTestCriticality"]["edges"]) == 1
    assert (
        result.data["ProfileTestCriticality"]["edges"][0]["node"]["display_label"]
        == f"ProfileTestCriticality(ID: {obj1.id})"
    )


async def test_upsert_profile_in_schema(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile = registry.schema.get("ProfileTestCriticality", branch=default_branch)

    obj1 = await Node.init(db=db, schema=profile)
    await obj1.new(db=db, profile_name="prof1", level=8)
    await obj1.save(db=db)

    query = """
    mutation {
        ProfileTestCriticalityUpsert(
            data: {
                profile_name: { value: "prof1"},
                level: { value: 10 }
                profile_priority: { value: 1234 }
            }
        ) {
            ok
            object {
                profile_name { value }
                level { value }
                profile_priority { value }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["ProfileTestCriticalityUpsert"]["ok"] is True
    gql_object = result.data["ProfileTestCriticalityUpsert"]["object"]
    assert gql_object["profile_name"]["value"] == "prof1"
    assert gql_object["level"]["value"] == 10
    assert gql_object["profile_priority"]["value"] == 1234
    retrieved_object = await NodeManager.get_one(db=db, id=obj1.id)
    assert retrieved_object.profile_name.value == "prof1"
    assert retrieved_object.level.value == 10
    assert retrieved_object.profile_priority.value == 1234


async def test_profile_apply(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=default_branch)
    prof_1 = await Node.init(db=db, schema=profile_schema)
    await prof_1.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await prof_1.save(db=db)
    prof_2 = await Node.init(db=db, schema=profile_schema)
    await prof_2.new(db=db, profile_name="prof2", profile_priority=2, level=9)
    await prof_2.save(db=db)

    crit_schema = registry.schema.get("TestCriticality", branch=default_branch)
    crit_1 = await Node.init(db=db, schema=crit_schema)
    await crit_1.new(db=db, name="crit_1")
    crit_1.level.is_default = True
    await crit_1.profiles.update(db=db, data=[prof_1])
    await crit_1.save(db=db)
    crit_2 = await Node.init(db=db, schema=crit_schema)
    await crit_2.new(db=db, name="crit_2")
    crit_2.level.is_default = True
    await crit_2.profiles.update(db=db, data=[prof_2])
    await crit_2.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    name { value }
                    level { value }
                    id
                    profiles{
                        edges {
                            node{ id }
                        }
                    }
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    crits = result.data["TestCriticality"]["edges"]
    assert len(crits) == 2
    assert {
        "node": {
            "name": {"value": "crit_1"},
            "level": {"value": 8},
            "id": crit_1.id,
            "profiles": {"edges": [{"node": {"id": prof_1.id}}]},
        }
    } in crits
    assert {
        "node": {
            "name": {"value": "crit_2"},
            "level": {"value": 9},
            "id": crit_2.id,
            "profiles": {"edges": [{"node": {"id": prof_2.id}}]},
        }
    } in crits


async def test_is_from_profile_set_correctly(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=default_branch)
    prof_1 = await Node.init(db=db, schema=profile_schema)
    await prof_1.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await prof_1.save(db=db)
    prof_2 = await Node.init(db=db, schema=profile_schema)
    await prof_2.new(db=db, profile_name="prof2", profile_priority=2, level=9, fancy="sometimes")
    await prof_2.save(db=db)

    crit_schema = registry.schema.get("TestCriticality", branch=default_branch)
    crit_no_profile = await Node.init(db=db, schema=crit_schema)
    await crit_no_profile.new(db=db, name="crit_no_profile")
    crit_no_profile.level.is_default = True
    crit_no_profile.fancy.value = "always"
    await crit_no_profile.save(db=db)

    crit_1_profile = await Node.init(db=db, schema=crit_schema)
    await crit_1_profile.new(db=db, name="crit_1_profile")
    crit_1_profile.level.is_default = True
    crit_1_profile.fancy.value = "never"
    await crit_1_profile.profiles.update(db=db, data=[prof_1])
    await crit_1_profile.save(db=db)

    crit_2_profile = await Node.init(db=db, schema=crit_schema)
    await crit_2_profile.new(db=db, name="crit_2_profile")
    crit_2_profile.level.value = 7
    crit_2_profile.fancy.is_default = True
    await crit_2_profile.profiles.update(db=db, data=[prof_1, prof_2])
    await crit_2_profile.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    name { value, is_from_profile }
                    level { value, is_from_profile }
                    fancy { value, is_from_profile }
                    id
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    crits = result.data["TestCriticality"]["edges"]
    assert len(crits) == 3
    assert {
        "node": {
            "name": {"value": "crit_no_profile", "is_from_profile": False},
            "level": {"value": None, "is_from_profile": False},
            "fancy": {"value": "always", "is_from_profile": False},
            "id": crit_no_profile.id,
        }
    } in crits
    assert {
        "node": {
            "name": {"value": "crit_1_profile", "is_from_profile": False},
            "level": {"value": 8, "is_from_profile": True},
            "fancy": {"value": "never", "is_from_profile": False},
            "id": crit_1_profile.id,
        }
    } in crits
    assert {
        "node": {
            "name": {"value": "crit_2_profile", "is_from_profile": False},
            "level": {"value": 7, "is_from_profile": False},
            "fancy": {"value": "sometimes", "is_from_profile": True},
            "id": crit_2_profile.id,
        }
    } in crits
