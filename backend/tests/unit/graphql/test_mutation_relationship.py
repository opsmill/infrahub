import pytest
from graphql import graphql
from infrahub_sdk import UUIDT

from infrahub.core.branch.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_relationship_add(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
        ]
    )

    # --------------------------------------
    # Add a Third member
    # --------------------------------------
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
        tag_red_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
            tag_red_main.id,
        ]
    )


async def test_relationship_remove(
    db: InfrahubDatabase,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_red_main.id,
        ]
    )

    # --------------------------------------
    # remove the second one
    # --------------------------------------
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
        tag_red_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(db=db, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(db=db)
    assert [tag.peer_id for tag in tags] == sorted([])


async def test_relationship_wrong_name(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "notvalid",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'notvalid' is not a valid relationship for 'TestPerson'"

    # Relationship existing relationship with the wrong cardinality
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "primary_tag",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == "'primary_tag' must be a relationship of cardinality Many"


async def test_relationship_wrong_node(
    db: InfrahubDatabase,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    # Non existing Node
    bad_uuid = str(UUIDT())
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        bad_uuid,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == f"'{bad_uuid}': Unable to find the node in the database."

    # Wrong Kind
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        person_jack_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert (
        result.errors[0].message == f"'{person_jack_main.id}' 'TestPerson' is not a valid peer for '{InfrahubKind.TAG}'"
    )


async def test_relationship_groups_add(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "members",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        c2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 3

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 2


async def test_relationship_groups_remove(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2, c3])
    await g2.save(db=db)

    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "members",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        c1.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 0

    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 0

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1


async def test_relationship_groups_add_remove(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data):
    c1 = car_person_generics_data["c1"]
    c2 = car_person_generics_data["c2"]
    c3 = car_person_generics_data["c3"]

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[c1])
    await g1.save(db=db)
    g2 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g2.new(db=db, name="group2", members=[c2])
    await g2.save(db=db)

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 4

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipAdd(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 8

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 2

    nbr_rels_before = await count_relationships(db=db)
    query = """
    mutation {
        RelationshipRemove(data: {
            id: "%s",
            name: "member_of_groups",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        c3.id,
        g1.id,
        g2.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after - nbr_rels_before == 4

    group1 = await NodeManager.get_one(db=db, id=g1.id, branch=default_branch)
    members = await group1.members.get(db=db)
    assert len(members) == 1

    group2 = await NodeManager.get_one(db=db, id=g2.id, branch=default_branch)
    members = await group2.members.get(db=db)
    assert len(members) == 1
