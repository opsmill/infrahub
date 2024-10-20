import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params


@pytest.fixture
def criticality_schema(default_branch: Branch, data_schema, node_group_schema):
    GENERIC_SCHEMA = {
        "name": "GenericCriticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }
    generic_schema = GenericSchema(**GENERIC_SCHEMA)
    registry.schema.set(name=generic_schema.kind, schema=generic_schema)

    NODE_SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "inherit_from": [generic_schema.kind],
        "attributes": [
            {"name": "fancy", "kind": "Text", "optional": True},
        ],
    }
    tmp_schema = NodeSchema(**NODE_SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)

    NODE_SCHEMA = {
        "name": "ColorfulCriticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "inherit_from": [generic_schema.kind],
        "attributes": [
            {"name": "color", "kind": "Text", "optional": True},
        ],
    }
    tmp_schema = NodeSchema(**NODE_SCHEMA)
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
    assert result.data["ProfileTestCriticality"]["edges"][0]["node"]["display_label"] == obj1.profile_name.value


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
                    profiles {
                        edges {
                            node { id }
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


async def test_profile_apply_generic(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile_generic_schema = registry.schema.get("ProfileTestGenericCriticality", branch=default_branch)
    prof_1 = await Node.init(db=db, schema=profile_generic_schema)
    await prof_1.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await prof_1.save(db=db)
    prof_2 = await Node.init(db=db, schema=profile_generic_schema)
    await prof_2.new(db=db, profile_name="prof2", profile_priority=2, level=9)
    await prof_2.save(db=db)

    crit_schema = registry.schema.get("TestCriticality", branch=default_branch)
    crit_1 = await Node.init(db=db, schema=crit_schema)
    await crit_1.new(db=db, name="crit_1")
    crit_1.level.is_default = True
    await crit_1.profiles.update(db=db, data=[prof_1])
    await crit_1.save(db=db)
    colorful_crit_schema = registry.schema.get("TestColorfulCriticality", branch=default_branch)
    crit_2 = await Node.init(db=db, schema=colorful_crit_schema)
    await crit_2.new(db=db, name="crit_2", color="green")
    crit_2.level.is_default = True
    await crit_2.profiles.update(db=db, data=[prof_2])
    await crit_2.save(db=db)

    query = """
    query {
        TestGenericCriticality {
            edges {
                node {
                    __typename
                    name { value }
                    level { value }
                    id
                    profiles {
                        edges {
                            node { id }
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
    crits = result.data["TestGenericCriticality"]["edges"]
    assert len(crits) == 2
    assert {
        "node": {
            "__typename": "TestCriticality",
            "name": {"value": "crit_1"},
            "level": {"value": 8},
            "id": crit_1.id,
            "profiles": {"edges": [{"node": {"id": prof_1.id}}]},
        }
    } in crits
    assert {
        "node": {
            "__typename": "TestColorfulCriticality",
            "name": {"value": "crit_2"},
            "level": {"value": 9},
            "id": crit_2.id,
            "profiles": {"edges": [{"node": {"id": prof_2.id}}]},
        }
    } in crits


async def test_setting_illegal_profiles_raises_error(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile_generic_schema = registry.schema.get(
        "ProfileTestGenericCriticality", branch=default_branch, duplicate=False
    )
    generic_profile = await Node.init(db=db, schema=profile_generic_schema)
    await generic_profile.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await generic_profile.save(db=db)
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=default_branch, duplicate=False)
    node_profile = await Node.init(db=db, schema=profile_schema)
    await node_profile.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await node_profile.save(db=db)
    generic_schema = registry.schema.get("TestGenericCriticality", branch=default_branch, duplicate=False)
    crit_schema = registry.schema.get("TestCriticality", branch=default_branch, duplicate=False)
    crit_1 = await Node.init(db=db, schema=crit_schema)
    await crit_1.new(db=db, name="crit_1")
    await crit_1.save(db=db)

    query = """
    mutation UpdateCrit($crit_id: String!, $prof_id: String!){
        TestCriticalityUpdate(data: {id: $crit_id, profiles: [{id: $prof_id}]})
        {
            ok
            object {
                profiles {
                    edges {
                        node {
                            id
                        }
                    }
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_mutation=True, include_subscription=False, branch=default_branch)

    crit_schema.generate_profile = False
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"crit_id": crit_1.id, "prof_id": node_profile.id},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "TestCriticality does not allow profiles" in result.errors[0].message

    generic_schema.generate_profile = False
    crit_schema.generate_profile = True
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"crit_id": crit_1.id, "prof_id": generic_profile.id},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert f"{generic_profile.id} is of kind ProfileTestGenericCriticality" in result.errors[0].message
    assert "only ['ProfileTestCriticality'] are allowed" in result.errors[0].message

    generic_schema.generate_profile = True
    crit_schema.generate_profile = True
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"crit_id": crit_1.id, "prof_id": generic_profile.id},
    )
    assert result.errors is None
    assert result.data["TestCriticalityUpdate"]["ok"] is True
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"crit_id": crit_1.id, "prof_id": node_profile.id},
    )
    assert result.errors is None
    assert result.data["TestCriticalityUpdate"]["ok"] is True
    assert result.data["TestCriticalityUpdate"]["object"] == {
        "profiles": {"edges": [{"node": {"id": node_profile.id}}]}
    }


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
    await crit_no_profile.new(db=db, name="crit_no_profile", fancy="always")
    await crit_no_profile.save(db=db)

    crit_1_profile = await Node.init(db=db, schema=crit_schema)
    await crit_1_profile.new(db=db, name="crit_1_profile", fancy="never")
    await crit_1_profile.profiles.update(db=db, data=[prof_1])
    await crit_1_profile.save(db=db)

    crit_2_profile = await Node.init(db=db, schema=crit_schema)
    await crit_2_profile.new(db=db, name="crit_2_profile", level=7)
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
    crits_by_id = {crit["node"]["id"]: crit["node"] for crit in crits}
    assert crits_by_id[crit_no_profile.id] == {
        "name": {"value": "crit_no_profile", "is_from_profile": False},
        "level": {"value": None, "is_from_profile": False},
        "fancy": {"value": "always", "is_from_profile": False},
        "id": crit_no_profile.id,
    }

    assert crits_by_id[crit_1_profile.id] == {
        "name": {"value": "crit_1_profile", "is_from_profile": False},
        "level": {"value": 8, "is_from_profile": True},
        "fancy": {"value": "never", "is_from_profile": False},
        "id": crit_1_profile.id,
    }

    assert crits_by_id[crit_2_profile.id] == {
        "name": {"value": "crit_2_profile", "is_from_profile": False},
        "level": {"value": 7, "is_from_profile": False},
        "fancy": {"value": "sometimes", "is_from_profile": True},
        "id": crit_2_profile.id,
    }

    assert crit_1_profile.id in gql_params.context.related_node_ids
    assert crit_2_profile.id in gql_params.context.related_node_ids


async def test_is_profile_source_set_correctly(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=default_branch)
    prof_1 = await Node.init(db=db, schema=profile_schema)
    await prof_1.new(db=db, profile_name="prof1", profile_priority=1, level=8)
    await prof_1.save(db=db)
    prof_2 = await Node.init(db=db, schema=profile_schema)
    await prof_2.new(db=db, profile_name="prof2", profile_priority=2, level=9, fancy="sometimes")
    await prof_2.save(db=db)

    crit_schema = registry.schema.get("TestCriticality", branch=default_branch)
    crit_no_profile = await Node.init(db=db, schema=crit_schema)
    await crit_no_profile.new(db=db, name="crit_no_profile", fancy="always")
    await crit_no_profile.save(db=db)

    crit_1_profile = await Node.init(db=db, schema=crit_schema)
    await crit_1_profile.new(db=db, name="crit_1_profile", fancy="never")
    await crit_1_profile.profiles.update(db=db, data=[prof_1])
    await crit_1_profile.save(db=db)

    crit_2_profile = await Node.init(db=db, schema=crit_schema)
    await crit_2_profile.new(db=db, name="crit_2_profile", level=7)
    await crit_2_profile.profiles.update(db=db, data=[prof_1, prof_2])
    await crit_2_profile.save(db=db)

    query = """
    query {
        TestCriticality {
            edges {
                node {
                    id
                    name {
                        value
                        is_from_profile
                        source {
                            id
                            display_label
                            __typename
                        }
                    }
                    level {
                        value
                        is_from_profile
                        source {
                            id
                            display_label
                            __typename
                        }
                    }
                    fancy {
                        value
                        is_from_profile
                        source {
                            id
                            display_label
                            __typename
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
    assert len(crits) == 3
    crits_by_id = {crit["node"]["id"]: crit["node"] for crit in crits}

    assert crits_by_id[crit_no_profile.id] == {
        "name": {"value": "crit_no_profile", "is_from_profile": False, "source": None},
        "level": {"value": None, "is_from_profile": False, "source": None},
        "fancy": {"value": "always", "is_from_profile": False, "source": None},
        "id": crit_no_profile.id,
    }

    assert crits_by_id[crit_1_profile.id] == {
        "name": {"value": "crit_1_profile", "is_from_profile": False, "source": None},
        "level": {
            "value": 8,
            "is_from_profile": True,
            "source": {
                "id": prof_1.id,
                "display_label": await prof_1.render_display_label(db=db),
                "__typename": "ProfileTestCriticality",
            },
        },
        "fancy": {"value": "never", "is_from_profile": False, "source": None},
        "id": crit_1_profile.id,
    }

    assert crits_by_id[crit_2_profile.id] == {
        "name": {"value": "crit_2_profile", "is_from_profile": False, "source": None},
        "level": {"value": 7, "is_from_profile": False, "source": None},
        "fancy": {
            "value": "sometimes",
            "is_from_profile": True,
            "source": {
                "id": prof_2.id,
                "display_label": await prof_2.render_display_label(db=db),
                "__typename": "ProfileTestCriticality",
            },
        },
        "id": crit_2_profile.id,
    }
