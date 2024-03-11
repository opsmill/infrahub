import pytest
from deepdiff import DeepDiff
from graphql import graphql

from infrahub import __version__, config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_info_query(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    query = """
    query {
        InfrahubInfo {
            version
        }
    }
    """

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=query,
        context_value=params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["InfrahubInfo"]["version"] == __version__


async def test_simple_query(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality {
            count
            edges {
                node {
                    name {
                        value
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
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert gql_params.context.related_node_ids == {obj1.id, obj2.id}


async def test_simple_query_with_offset_and_limit(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality(offset: 0, limit:1) {
            count
            edges {
                node {
                    name {
                        value
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
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 1


async def test_display_label_one_item(db: InfrahubDatabase, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
        ],
    }
    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)
    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low")
    await obj1.save(db=db)

    query = """
    query {
        TestCriticality {
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
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == "Low"


async def test_display_label_multiple_items(db: InfrahubDatabase, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "display_labels": ["name__value", "level__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)

    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=schema)
    await obj2.new(db=db, name="medium", level=3)
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality {
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
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert sorted([node["node"]["display_label"] for node in result.data["TestCriticality"]["edges"]]) == [
        "low 4",
        "medium 3",
    ]


async def test_display_label_default_value(db: InfrahubDatabase, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema = registry.schema.get(tmp_schema.kind, branch=default_branch)

    obj1 = await Node.init(db=db, schema=schema)
    await obj1.new(db=db, name="low")
    await obj1.save(db=db)

    query = """
    query {
        TestCriticality {
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
    assert len(result.data["TestCriticality"]["edges"]) == 1
    assert result.data["TestCriticality"]["edges"][0]["node"]["display_label"] == f"TestCriticality(ID: {obj1.id})"


async def test_all_attributes(db: InfrahubDatabase, default_branch: Branch, data_schema, all_attribute_types_schema):
    obj1 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj1.new(
        db=db,
        name="obj1",
        mystring="abc",
        mybool=False,
        myint=123,
        mylist=["1", 2, False],
        myjson={"key1": "bill"},
    )
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj2.new(db=db, name="obj2")
    await obj2.save(db=db)

    query = """
    query {
        TestAllAttributeTypes {
            edges {
                node {
                    name { value }
                    mystring { value }
                    mybool { value }
                    myint { value }
                    mylist { value }
                    myjson { value }
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
    assert len(result.data["TestAllAttributeTypes"]["edges"]) == 2

    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestAllAttributeTypes"]["edges"]}

    assert results["obj1"]["mystring"]["value"] == obj1.mystring.value
    assert results["obj1"]["mybool"]["value"] == obj1.mybool.value
    assert results["obj1"]["myint"]["value"] == obj1.myint.value
    assert results["obj1"]["mylist"]["value"] == obj1.mylist.value
    assert results["obj1"]["myjson"]["value"] == obj1.myjson.value

    assert results["obj2"]["mystring"]["value"] == obj2.mystring.value
    assert results["obj2"]["mybool"]["value"] == obj2.mybool.value
    assert results["obj2"]["myint"]["value"] == obj2.myint.value
    assert results["obj2"]["mylist"]["value"] == obj2.mylist.value
    assert results["obj2"]["myjson"]["value"] == obj2.myjson.value


async def test_nested_query(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1
    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, c3.id}


async def test_double_nested_query(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                                owner {
                                    node {
                                        name {
                                            value
                                        }
                                    }
                                }
                            }
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

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["cars"]["edges"]) == 1
    assert result_per_name["John"]["cars"]["count"] == 2
    assert result_per_name["Jane"]["cars"]["count"] == 1
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["node"]["name"]["value"] == "John"

    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, c3.id}


async def test_display_label_nested_query(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                id
                                display_label
                                owner {
                                    node {
                                        id
                                        display_label
                                    }
                                }
                            }
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

    expected_result = {
        "cars": {
            "edges": [
                {
                    "node": {
                        "display_label": "volt #444444",
                        "id": str(c1.id),
                        "owner": {
                            "node": {
                                "display_label": "John",
                                "id": str(p1.id),
                            }
                        },
                    }
                },
                {
                    "node": {
                        "display_label": "bolt #444444",
                        "id": str(c2.id),
                        "owner": {
                            "node": {
                                "display_label": "John",
                                "id": str(p1.id),
                            }
                        },
                    }
                },
            ],
        },
        "name": {"value": "John"},
    }

    assert DeepDiff(result.data["TestPerson"]["edges"][0]["node"], expected_result, ignore_order=True).to_dict() == {}


def _check_diff_for_branch_and_id(all_dicts: list[dict], branch_name: str, id: str, things_to_check: dict) -> dict:
    this_dict = None
    for one_dict in all_dicts:
        if one_dict["branch"] == branch_name and one_dict["id"] == id:
            this_dict = one_dict
            break
    if not this_dict:
        raise ValueError(f"No diff for branch={branch_name} and id={id}")
    for key, value in things_to_check.items():
        assert this_dict.get(key) == value
    return this_dict


async def test_query_diffsummary_old(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1_main = await Node.init(db=db, schema=person)
    await p1_main.new(db=db, name="John", height=180)
    await p1_main.save(db=db)
    p2_main = await Node.init(db=db, schema=person)
    await p2_main.new(db=db, name="Jane", height=170)
    await p2_main.save(db=db)

    c1_main = await Node.init(db=db, schema=car)
    await c1_main.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1_main)
    await c1_main.save(db=db)
    c2_main = await Node.init(db=db, schema=car)
    await c2_main.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1_main)
    await c2_main.save(db=db)
    c3_main = await Node.init(db=db, schema=car)
    await c3_main.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2_main)
    await c3_main.save(db=db)

    branch2 = await create_branch(branch_name="branch2", db=db)
    await c1_main.delete(db=db)
    p1_branch2 = await NodeManager.get_one_by_id_or_default_filter(
        id=p1_main.id, db=db, schema_name="TestPerson", branch=branch2
    )
    p1_branch2.name.value = "Jonathan"
    await p1_branch2.save(db=db)
    p2_main.name.value = "Jeanette"
    await p2_main.save(db=db)
    c2_main.name.value = "bolting"
    await c2_main.save(db=db)
    c3_branch2 = await NodeManager.get_one_by_id_or_default_filter(
        id=c3_main.id, db=db, schema_name="TestCar", branch=branch2
    )
    await c3_branch2.owner.update(data=p1_branch2.id, db=db)
    await c3_branch2.save(db=db)

    query = """
    query {
        DiffSummaryOld {
            branch
            node
            kind
            actions
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=branch2)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    diff_summary = result.data["DiffSummaryOld"]
    assert len(diff_summary) == 7

    assert {"branch": "main", "node": c1_main.id, "kind": "TestCar", "actions": ["removed"]} in diff_summary
    assert {"branch": "main", "node": c2_main.id, "kind": "TestCar", "actions": ["updated"]} in diff_summary
    assert {"branch": "branch2", "node": c3_branch2.id, "kind": "TestCar", "actions": ["updated"]} in diff_summary
    assert {"branch": "main", "node": p2_main.id, "kind": "TestPerson", "actions": ["updated"]} in diff_summary
    assert {"branch": "branch2", "node": p1_branch2.id, "kind": "TestPerson", "actions": ["updated"]} in diff_summary


async def test_query_diffsummary(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1_main = await Node.init(db=db, schema=person)
    await p1_main.new(db=db, name="John", height=180)
    await p1_main.save(db=db)
    p2_main = await Node.init(db=db, schema=person)
    await p2_main.new(db=db, name="Jane", height=170)
    await p2_main.save(db=db)

    c1_main = await Node.init(db=db, schema=car)
    await c1_main.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1_main)
    await c1_main.save(db=db)
    c2_main = await Node.init(db=db, schema=car)
    await c2_main.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1_main)
    await c2_main.save(db=db)
    c3_main = await Node.init(db=db, schema=car)
    await c3_main.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2_main)
    await c3_main.save(db=db)

    branch2 = await create_branch(branch_name="branch2", db=db)
    await c1_main.delete(db=db)
    p1_branch2 = await NodeManager.get_one_by_id_or_default_filter(
        id=p1_main.id, db=db, schema_name="TestPerson", branch=branch2
    )
    p1_branch2.name.value = "Jonathan"
    await p1_branch2.save(db=db)
    p2_main.name.value = "Jeanette"
    await p2_main.save(db=db)
    c2_main.name.value = "bolting"
    await c2_main.save(db=db)
    c3_branch2 = await NodeManager.get_one_by_id_or_default_filter(
        id=c3_main.id, db=db, schema_name="TestCar", branch=branch2
    )
    await c3_branch2.owner.update(data=p1_branch2.id, db=db)
    await c3_branch2.save(db=db)

    query = """
        query {
            DiffSummary {
                branch
                id
                kind
                action
                display_label
                elements {
                    element_type
                    name
                    action
                    summary {
                        added
                        updated
                        removed
                    }
                    ... on DiffSummaryElementRelationshipMany {
                        peers {
                            action
                            summary {
                                added
                                updated
                                removed
                            }
                        }
                    }
                }
            }
        }
    """
    gql_params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=branch2)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    diff_summary = result.data["DiffSummary"]

    assert len(diff_summary) == 5

    _check_diff_for_branch_and_id(
        all_dicts=diff_summary,
        branch_name="main",
        id=c1_main.id,
        things_to_check={
            "branch": "main",
            "id": c1_main.id,
            "kind": "TestCar",
            "action": "REMOVED",
            "display_label": "",
        },
    )
    _check_diff_for_branch_and_id(
        all_dicts=diff_summary,
        branch_name="main",
        id=c2_main.id,
        things_to_check={
            "branch": "main",
            "id": c2_main.id,
            "kind": "TestCar",
            "action": "UPDATED",
            "display_label": "bolting #444444",
            "elements": [
                {
                    "element_type": "ATTRIBUTE",
                    "name": "name",
                    "action": "UPDATED",
                    "summary": {"added": 0, "updated": 1, "removed": 0},
                }
            ],
        },
    )
    c3_branch2_diff = _check_diff_for_branch_and_id(
        all_dicts=diff_summary,
        branch_name="branch2",
        id=c3_branch2.id,
        things_to_check={
            "branch": "branch2",
            "id": c3_branch2.id,
            "kind": "TestCar",
            "action": "UPDATED",
            "display_label": "nolt #444444",
        },
    )
    c3_branch2_diff_elements = c3_branch2_diff["elements"]
    assert len(c3_branch2_diff_elements) == 1
    assert c3_branch2_diff_elements[0]["element_type"] == "RELATIONSHIP_ONE"
    assert c3_branch2_diff_elements[0]["name"] == "owner"
    assert c3_branch2_diff_elements[0]["action"] == "UPDATED"
    p2_main_diff = _check_diff_for_branch_and_id(
        all_dicts=diff_summary,
        branch_name="main",
        id=p2_main.id,
        things_to_check={
            "branch": "main",
            "id": p2_main.id,
            "kind": "TestPerson",
            "action": "UPDATED",
            "display_label": "Jeanette",
        },
    )
    p2_main_diff_elements = p2_main_diff["elements"]
    assert len(p2_main_diff_elements) == 1
    assert p2_main_diff_elements[0]["element_type"] == "ATTRIBUTE"
    assert p2_main_diff_elements[0]["name"] == "name"
    assert p2_main_diff_elements[0]["action"] == "UPDATED"
    assert p2_main_diff_elements[0]["summary"] == {"added": 0, "updated": 1, "removed": 0}
    p1_branch2_diff = _check_diff_for_branch_and_id(
        all_dicts=diff_summary,
        branch_name="branch2",
        id=p1_branch2.id,
        things_to_check={
            "branch": "branch2",
            "id": p1_branch2.id,
            "kind": "TestPerson",
            "action": "UPDATED",
            "display_label": "Jonathan",
        },
    )
    p1_branch2_diff_elements = p1_branch2_diff["elements"]
    assert len(p1_branch2_diff_elements) == 2
    p1_branch2_diff_elements_map = {elem["name"]: elem for elem in p1_branch2_diff_elements}
    assert {"cars", "name"} == set(p1_branch2_diff_elements_map.keys())
    name_element = p1_branch2_diff_elements_map["name"]
    assert name_element["name"] == "name"
    assert name_element["element_type"] == "ATTRIBUTE"
    assert name_element["action"] == "UPDATED"
    cars_element = p1_branch2_diff_elements_map["cars"]
    assert cars_element["name"] == "cars"
    assert cars_element["element_type"] == "RELATIONSHIP_MANY"
    assert cars_element["action"] == "ADDED"
    assert len(cars_element["peers"]) == 1
    assert cars_element["peers"][0]["action"] == "ADDED"


async def test_query_typename(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson {
        __typename
            edges {
            __typename
                node {
                    __typename
                    name {
                        value
                        __typename
                    }
                    cars {
                    __typename
                        edges {
                        __typename
                            properties {
                                __typename
                            }
                            node {
                                __typename
                                name {
                                    __typename
                                    value
                                }
                                owner {
                                    __typename
                                    node {
                                        __typename
                                        name {
                                            value
                                            __typename
                                        }
                                    }
                                }
                            }
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

    result_per_name = {result["node"]["name"]["value"]: result["node"] for result in result.data["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert result.data["TestPerson"]["__typename"] == "PaginatedTestPerson"
    assert result.data["TestPerson"]["edges"][0]["__typename"] == "EdgedTestPerson"
    assert result.data["TestPerson"]["edges"][0]["node"]["__typename"] == "TestPerson"
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["__typename"] == "TextAttribute"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["__typename"] == "TestCar"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["__typename"] == "NestedEdgedTestPerson"
    assert result_per_name["John"]["cars"]["edges"][0]["node"]["owner"]["node"]["name"]["__typename"] == "TextAttribute"
    assert result_per_name["John"]["cars"]["edges"][0]["properties"]["__typename"] == "RelationshipProperty"


async def test_query_filter_ids(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)
    obj3 = await Node.init(db=db, schema=criticality_schema)
    await obj3.new(db=db, name="high", level=1, description="My desc", color="#222222")
    await obj3.save(db=db)

    query = (
        """
    query {
        TestCriticality(ids: ["%s"]) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
        % obj1.id
    )
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
    assert len(result.data["TestCriticality"]["edges"]) == 1

    query = """
    query {
        TestCriticality(ids: ["%s", "%s"]) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        obj1.id,
        obj2.id,
    )
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
    assert len(result.data["TestCriticality"]["edges"]) == 2


async def test_query_filter_local_attrs(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality(name__value: "low") {
            edges {
                node {
                    name {
                        value
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
    assert len(result.data["TestCriticality"]["edges"]) == 1


@pytest.mark.parametrize("graphql_enums_on,enum_value", [(True, "MANUAL"), (False, '"manual"')])
async def test_query_filter_on_enum(
    db: InfrahubDatabase, default_branch: Branch, person_john_main, car_person_schema, graphql_enums_on, enum_value
):
    config.SETTINGS.experimental_features.graphql_enums = graphql_enums_on
    car = registry.schema.get(name="TestCar")

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="GoKart", nbr_seats=1, is_electric=True, owner=person_john_main, transmission="manual")
    await c1.save(db=db)

    query = """
    query {
        TestCar(transmission__value: %s) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (enum_value)
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
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["name"]["value"] == "GoKart"


async def test_query_multiple_filters(db: InfrahubDatabase, default_branch: Branch, car_person_manufacturer_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")
    manufacturer = registry.schema.get(name="TestManufacturer")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    m1 = await Node.init(db=db, schema=manufacturer)
    await m1.new(db=db, name="chevrolet")
    await m1.save(db=db)
    m2 = await Node.init(db=db, schema=manufacturer)
    await m2.new(db=db, name="ford", description="from Michigan")
    await m2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=False, owner=p1, manufacturer=m1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=3, is_electric=True, owner=p1, manufacturer=m2)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2, manufacturer=m1)
    await c3.save(db=db)

    query01 = """
    query {
        TestCar(owner__name__value: "John", nbr_seats__value: 4) {
            edges {
                node {
                    id
                    name {
                        value
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
        source=query01,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c1.id

    query02 = """
    query {
        TestCar(is_electric__value: true, nbr_seats__value: 4) {
            edges {
                node {
                    id
                    name {
                        value
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
        source=query02,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c3.id

    query03 = """
    query {
        TestCar(owner__name__value: "John", manufacturer__name__value: "ford") {
            edges {
                node {
                    id
                    name {
                        value
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
        source=query03,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id

    query04 = """
    query {
        TestCar(owner__ids: ["%s"], manufacturer__ids: ["%s"]) {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        m2.id,
    )
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query04,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["TestCar"]["edges"]) == 1
    assert result.data["TestCar"]["edges"][0]["node"]["id"] == c2.id


async def test_query_filter_relationships(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query = """
    query {
        TestPerson(name__value: "John") {
            count
            edges {
                node {
                    name {
                        value
                    }
                    cars(name__value: "volt") {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["count"] == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationships_with_generic(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data
):
    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(name__value: "volt") {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"


async def test_query_filter_relationships_with_generic_filter(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data
):
    query = """
    query {
        TestPerson(cars__name__value: "volt") {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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

    expected_results = [
        {
            "node": {
                "name": {"value": "John"},
                "cars": {"edges": [{"node": {"name": {"value": "bolt"}}}, {"node": {"name": {"value": "volt"}}}]},
            }
        }
    ]
    assert DeepDiff(result.data["TestPerson"]["edges"], expected_results, ignore_order=True).to_dict() == {}


async def test_query_filter_relationship_id(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)
    c4 = await Node.init(db=db, schema=car)
    await c4.new(db=db, name="yaris", nbr_seats=5, is_electric=False, owner=p1)
    await c4.save(db=db)

    query = (
        """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(ids: ["%s"]) {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
        % c1.id
    )
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
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"

    query = """
    query {
        TestPerson(name__value: "John") {
            edges {
                node {
                    name {
                        value
                    }
                    cars(ids: ["%s", "%s"]) {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """ % (
        c1.id,
        c4.id,
    )
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
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0]["node"]["name"]["value"] == "John"
    assert len(result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]) == 2


async def test_query_attribute_multiple_values(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)

    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    query = """
    query {
        TestPerson(name__values: ["John", "Jane"]) {
            count
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
    assert result.data["TestPerson"]["count"] == 2


async def test_query_relationship_multiple_values(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)

    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(db=db, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(db=db, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema=car)
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)
    c4 = await Node.init(db=db, schema=car)
    await c4.new(db=db, name="yaris", nbr_seats=5, is_electric=False, owner=p1)
    await c4.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars (name__values: ["volt", "nolt"]) {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    assert len(result.data["TestPerson"]["edges"]) == 2
    assert result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert result.data["TestPerson"]["edges"][1]["node"]["cars"]["edges"][0]["node"]["name"]["value"] == "nolt"


async def test_query_oneway_relationship(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="Red")
    await t2.save(db=db)
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    tags {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    assert len(result.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2


async def test_query_at_specific_time(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="Red")
    await t2.save(db=db)

    time1 = Timestamp()

    t2.name.value = "Green"
    await t2.save(db=db)

    query = """
    query {
        BuiltinTag {
            edges {
                node {
                    name {
                        value
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
    assert len(result.data[InfrahubKind.TAG]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data[InfrahubKind.TAG]["edges"]])
    assert names == ["Blue", "Green"]

    # Now query at a specific time
    query = """
    query {
        BuiltinTag {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, at=time1, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data[InfrahubKind.TAG]["edges"]) == 2
    names = sorted([tag["node"]["name"]["value"] for tag in result.data[InfrahubKind.TAG]["edges"]])
    assert names == ["Blue", "Red"]


async def test_query_attribute_updated_at(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    p11 = await Node.init(db=db, schema="TestPerson")
    await p11.new(db=db, firstname="John", lastname="Doe")
    await p11.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        updated_at
                    }
                    lastname {
                        value
                        updated_at
                    }
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        == result1.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )

    p12 = await NodeManager.get_one(db=db, id=p11.id)
    p12.firstname.value = "Jim"
    await p12.save(db=db)

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result2 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["firstname"]["updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["lastname"]["updated_at"]
    )


async def test_query_node_updated_at(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe")
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    _updated_at
                    id
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["_updated_at"]

    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, firstname="Jane", lastname="Doe")
    await p2.save(db=db)

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result2 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["TestPerson"]["edges"][0]["node"]["_updated_at"]
    assert result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
    assert (
        result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
        == Timestamp(result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]).to_string()
    )
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["_updated_at"]
        != result2.data["TestPerson"]["edges"][1]["node"]["_updated_at"]
    )


async def test_query_relationship_updated_at(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="Red")
    await t2.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    tags {
                        edges {
                            node {
                                _updated_at
                                name {
                                    value
                                }
                            }
                            properties {
                                updated_at
                            }
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
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"] == []

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(db=db)

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result2 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert len(result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"]) == 2
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        != result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["properties"]["updated_at"]
    )
    assert (
        result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        == Timestamp(
            result2.data["TestPerson"]["edges"][0]["node"]["tags"]["edges"][0]["node"]["_updated_at"]
        ).to_string()
    )


async def test_query_attribute_node_property_source(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        source {
                            name {
                                value
                            }
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
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["source"]["name"]["value"]
        == first_account.name.value
    )
    assert gql_params.context.related_node_ids == {p1.id, first_account.id}


async def test_query_attribute_node_property_owner(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", _owner=first_account)
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        owner {
                            name {
                                value
                            }
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
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["owner"]
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["owner"]["name"]["value"]
        == first_account.name.value
    )
    assert gql_params.context.related_node_ids == {p1.id, first_account.id}


async def test_query_relationship_node_property(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, first_account
):
    car = registry.schema.get(name="TestCar")
    person = registry.schema.get(name="TestPerson")

    p1 = await Node.init(db=db, schema=person)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema=person)
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)

    c1 = await Node.init(db=db, schema=car)
    await c1.new(
        db=db,
        name="volt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p1, "_relation__owner": first_account.id},
    )
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema=car)
    await c2.new(
        db=db,
        name="bolt",
        nbr_seats=4,
        is_electric=True,
        owner={"id": p2, "_relation__source": first_account.id},
    )
    await c2.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                            properties {
                                owner {
                                    id
                                }
                                source {
                                    id
                                }
                            }
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

    results = {item["node"]["name"]["value"]: item["node"] for item in result.data["TestPerson"]["edges"]}
    assert sorted(list(results.keys())) == ["Jane", "John"]
    assert len(results["John"]["cars"]["edges"]) == 1
    assert len(results["Jane"]["cars"]["edges"]) == 1

    assert results["John"]["cars"]["edges"][0]["node"]["name"]["value"] == "volt"
    assert results["John"]["cars"]["edges"][0]["properties"]["owner"]
    assert results["John"]["cars"]["edges"][0]["properties"]["owner"]["id"] == first_account.id
    assert results["John"]["cars"]["edges"][0]["properties"]["source"] is None

    assert results["Jane"]["cars"]["edges"][0]["node"]["name"]["value"] == "bolt"
    assert results["Jane"]["cars"]["edges"][0]["properties"]["owner"] is None
    assert results["Jane"]["cars"]["edges"][0]["properties"]["source"]
    assert results["Jane"]["cars"]["edges"][0]["properties"]["source"]["id"] == first_account.id
    assert gql_params.context.related_node_ids == {p1.id, p2.id, c1.id, c2.id, first_account.id}


async def test_query_attribute_flag_property(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(
        db=db,
        firstname={"value": "John", "is_protected": True},
        lastname={"value": "Doe", "is_visible": False},
        _source=first_account,
    )
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    id
                    firstname {
                        value
                        is_protected
                    }
                    lastname {
                        value
                        is_visible
                    }
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["firstname"]["is_protected"] is True
    assert result1.data["TestPerson"]["edges"][0]["node"]["lastname"]["is_visible"] is False


async def test_query_branches(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    query = """
    query {
        Branch {
            id
            name
            branched_from
            is_data_only
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["Branch"][0]["name"] == "main"


async def test_query_multiple_branches(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    query = """
    query {
        branch1: Branch {
            id
            name
            branched_from
            is_data_only
        }
        branch2: Branch {
            id
            name
            branched_from
            is_data_only
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["branch1"][0]["name"] == "main"
    assert result1.data["branch2"][0]["name"] == "main"


async def test_multiple_queries(db: InfrahubDatabase, default_branch: Branch, person_tag_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe")
    await p1.save(db=db)

    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, firstname="Jane", lastname="Doe")
    await p2.save(db=db)

    query = """
    query {
        firstperson: TestPerson(firstname__value: "John") {
            edges {
                node {
                    id
                    firstname {
                        value
                    }
                }
            }
        }
        secondperson: TestPerson(firstname__value: "Jane") {
            edges {
                node {
                    id
                    firstname {
                        value
                    }
                }
            }

        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["firstperson"]["edges"][0]["node"]["firstname"]["value"] == "John"
    assert result1.data["secondperson"]["edges"][0]["node"]["firstname"]["value"] == "Jane"
    assert gql_params.context.related_node_ids == {p1.id, p2.id}


async def test_model_node_interface(db: InfrahubDatabase, default_branch: Branch, car_schema):
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    d2 = await Node.init(db=db, schema="TestCar")
    await d2.new(db=db, name="Renaud Clio", nbr_doors=4)
    await d2.save(db=db)

    query = """
    query {
        TestCar {
            edges {
                node {
                    name {
                        value
                    }
                    description {
                        value
                    }
                    nbr_doors {
                        value
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
    assert sorted([car["node"]["name"]["value"] for car in result.data["TestCar"]["edges"]]) == [
        "Porsche 911",
        "Renaud Clio",
    ]
    assert sorted([car["node"]["nbr_doors"]["value"] for car in result.data["TestCar"]["edges"]]) == [2, 4]
    assert gql_params.context.related_node_ids == {d1.id, d2.id}


async def test_model_rel_interface(db: InfrahubDatabase, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    b1 = await Node.init(db=db, schema="TestBoat")
    await b1.new(db=db, name="Laser", has_sails=True)
    await b1.save(db=db)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John Doe", vehicules=[d1, b1])
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    vehicules {
                        edges {
                            node {
                                name {
                                    value
                                }
                                ... on TestCar {
                                    nbr_doors {
                                        value
                                    }
                                }
                                ... on TestBoat {
                                    has_sails {
                                        value
                                    }
                                }
                            }
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
    assert len(result.data["TestPerson"]["edges"][0]["node"]["vehicules"]["edges"]) == 2
    expected_results = {
        "name": {"value": "John Doe"},
        "vehicules": {
            "edges": [
                {"node": {"name": {"value": "Porsche 911"}, "nbr_doors": {"value": 2}}},
                {"node": {"has_sails": {"value": True}, "name": {"value": "Laser"}}},
            ]
        },
    }
    assert DeepDiff(result.data["TestPerson"]["edges"][0]["node"], expected_results, ignore_order=True).to_dict() == {}


async def test_model_rel_interface_reverse(db: InfrahubDatabase, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(db=db, schema="TestCar")
    await d1.new(db=db, name="Porsche 911", nbr_doors=2)
    await d1.save(db=db)

    b1 = await Node.init(db=db, schema="TestBoat")
    await b1.new(db=db, name="Laser", has_sails=True)
    await b1.save(db=db)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John Doe", vehicules=[d1, b1])
    await p1.save(db=db)

    query = """
    query {
        TestBoat {
            edges {
                node {
                    name {
                        value
                    }
                    owners {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    assert len(result.data["TestBoat"]["edges"][0]["node"]["owners"]["edges"]) == 1


async def test_generic_root_with_pagination(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    query = """
    query {
        TestCar(limit: 2) {
            count
            edges {
                node {
                    name {
                        value
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
    expected_response = {
        "TestCar": {
            "count": 3,
            "edges": [
                {"node": {"name": {"value": "bolt"}}},
                {"node": {"name": {"value": "nolt"}}},
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


async def test_generic_root_with_filters(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    query = """
    query {
        TestCar(owner__name__value: "John" ) {
            count
            edges {
                node {
                    name {
                        value
                    }
                }
            }

        }
    }
    """

    gql_params = prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    expected_response = {
        "TestCar": {
            "count": 2,
            "edges": [
                {"node": {"name": {"value": "bolt"}}},
                {"node": {"name": {"value": "volt"}}},
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


async def test_member_of_groups(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1, c2])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

    query = """
    query {
        TestCar {
            count
            edges {
                node {
                    name {
                        value
                    }
                    member_of_groups {
                        count
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
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
    expected_response = {
        "TestCar": {
            "count": 3,
            "edges": [
                {
                    "node": {
                        "member_of_groups": {
                            "count": 2,
                            "edges": [
                                {"node": {"name": {"value": "group1"}}},
                                {"node": {"name": {"value": "group2"}}},
                            ],
                        },
                        "name": {"value": "bolt"},
                    },
                },
                {
                    "node": {
                        "member_of_groups": {
                            "count": 1,
                            "edges": [{"node": {"name": {"value": "group2"}}}],
                        },
                        "name": {"value": "nolt"},
                    },
                },
                {
                    "node": {
                        "member_of_groups": {
                            "count": 1,
                            "edges": [{"node": {"name": {"value": "group1"}}}],
                        },
                        "name": {"value": "volt"},
                    },
                },
            ],
        },
    }
    assert result.errors is None
    assert DeepDiff(result.data, expected_response, ignore_order=True).to_dict() == {}


async def test_hierarchical_location_parent_filter(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data
):
    query = """
    query GetRack {
        LocationRack(parent__name__values: "europe") {
            edges {
                node {
                    id
                    display_label
                    name {
                        value
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

    nodes = [node["node"]["name"]["value"] for node in result.data["LocationRack"]["edges"]]

    assert result.errors is None
    assert nodes == ["paris-r1", "paris-r2", "london-r1", "london-r2"]


async def test_hierarchical_location_ancestors(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data
):
    query = """
    query {
        LocationRack(name__value: "paris-r1") {
            edges {
                node {
                    id
                    display_label
                    ancestors {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
                        }
                    }
                    descendants {
                        edges {
                            node {
                                id
                                display_label
                            }
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
    rack = result.data["LocationRack"]["edges"][0]["node"]
    ancestors = rack["ancestors"]["edges"]
    descendants = rack["descendants"]["edges"]
    ancestor_names = [node["node"]["name"]["value"] for node in ancestors]

    assert ancestor_names == ["europe", "paris"]
    assert descendants == []


async def test_hierarchical_location_descendants(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data
):
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
                        }
                    }
                    ancestors {
                        edges {
                            node {
                                id
                                display_label
                            }
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    ancestors = asia["ancestors"]["edges"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing",
        "beijing-r1",
        "beijing-r2",
        "singapore",
        "singapore-r1",
        "singapore-r2",
    ]
    assert ancestors == []


async def test_hierarchical_location_descendants_filters_attr(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data
):
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants(status__value: "offline") {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing-r2",
        "singapore-r2",
    ]


async def test_hierarchical_location_descendants_filters_ids(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data
):
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    descendants(ids: ["%s", "%s", "%s"]) {
                        edges {
                            node {
                                id
                                display_label
                                __typename
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """ % (
        hierarchical_location_data["beijing"].id,
        hierarchical_location_data["beijing-r1"].id,
        hierarchical_location_data["singapore-r2"].id,
    )
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    descendants = asia["descendants"]["edges"]
    descendants_names = [node["node"]["name"]["value"] for node in descendants]

    assert descendants_names == [
        "beijing",
        "beijing-r1",
        "singapore-r2",
    ]


async def test_hierarchical_location_include_descendants(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_thing
):
    query = """
    query {
        LocationRegion(name__value: "asia") {
            edges {
                node {
                    id
                    display_label
                    things(include_descendants: true) {
                        count
                        edges {
                            node {
                                id
                                display_label
                                name {
                                    value
                                }
                            }
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
    asia = result.data["LocationRegion"]["edges"][0]["node"]
    things = asia["things"]["edges"]
    things_names = [node["node"]["name"]["value"] for node in things]

    assert things_names == [
        "thing-asia",
        "thing-beijing",
        "thing-beijing-r1",
        "thing-beijing-r2",
        "thing-singapore",
        "thing-singapore-r1",
        "thing-singapore-r2",
    ]
    assert asia["things"]["count"] == 7


async def test_hierarchical_groups_descendants(db: InfrahubDatabase, default_branch: Branch, hierarchical_groups_data):
    query = """
    query {
        CoreStandardGroup(name__value: "grp1") {
            edges {
                node {
                    id
                    display_label
                    members(include_descendants: true) {
                        count
                        edges {
                            node {
                                id
                                display_label
                                __typename
                            }
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
    grp1 = result.data["CoreStandardGroup"]["edges"][0]["node"]
    members = grp1["members"]["edges"]
    members_ids = [node["node"]["id"] for node in members]

    member_names = [hierarchical_groups_data[member_id].name.value for member_id in members_ids]

    assert member_names == [
        "tag-0",
        "tag-1",
        "tag-2",
        "tag-3",
        "tag-4",
        "tag-5",
        "tag-6",
        "tag-7",
        "tag-8",
        "tag-9",
        "tag-10",
        "tag-11",
        "tag-12",
        "tag-13",
    ]
    assert grp1["members"]["count"] == 14
