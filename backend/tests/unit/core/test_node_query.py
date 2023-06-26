from neo4j import AsyncSession

from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch
from infrahub.core.group import Group
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeCreateQuery,
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetLocalAttributeValueQuery,
    NodeListGetRelationshipsQuery,
)
from infrahub.core.timestamp import Timestamp


async def test_query_NodeCreateQuery_with_generic(session: AsyncSession, group_schema, branch: Branch):
    obj = await Group.init(session=session, schema="StandardGroup", branch=branch)

    query = await NodeCreateQuery.init(session=session, node=obj)
    await query.execute(session=session)
    node = query.get_result().get("n")

    assert sorted(list(node.labels)) == sorted(["Group", "Node", "StandardGroup"])


async def test_query_NodeGetListQuery(
    session: AsyncSession, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="Person", branch=branch)
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id, person_alfred_main.id]
    query = await NodeGetListQuery.init(session=session, branch=branch, schema=person_schema)
    await query.execute(session=session)
    assert sorted(query.get_node_ids()) == sorted(ids)


async def test_query_NodeGetListQuery_filter_id(
    session: AsyncSession, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="Person", branch=branch)
    query = await NodeGetListQuery.init(
        session=session, branch=branch, schema=person_schema, filters={"id": person_john_main.id}
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_ids(
    session: AsyncSession, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="Person", branch=branch)
    person_schema.order_by = ["height__value"]
    query = await NodeGetListQuery.init(
        session=session,
        branch=branch,
        schema=person_schema,
        filters={"ids": [person_jim_main.id, person_john_main.id, person_albert_main.id]},
    )
    await query.execute(session=session)
    assert query.get_node_ids() == [person_albert_main.id, person_jim_main.id, person_john_main.id]


async def test_query_NodeGetListQuery_filter_height(
    session: AsyncSession, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    schema = registry.schema.get(name="Person", branch=branch)
    query = await NodeGetListQuery.init(session=session, branch=branch, schema=schema, filters={"height__value": 160})
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_boolean(
    session: AsyncSession, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="Car", branch=branch)
    query = await NodeGetListQuery.init(
        session=session, branch=branch, schema=schema, filters={"is_electric__value": False}
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 3


async def test_query_NodeGetListQuery_deleted_node(
    session: AsyncSession, car_accord_main, car_camry_main: Node, car_volt_main, car_yaris_main, branch: Branch
):
    node_to_delete = await NodeManager.get_one(id=car_camry_main.id, session=session, branch=branch)
    await node_to_delete.delete(session=session)

    schema = registry.schema.get(name="Car", branch=branch)
    schema.order_by = ["owner__name__value"]

    query = await NodeGetListQuery.init(
        session=session, branch=branch, schema=schema, filters={"is_electric__value": False}
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship(
    session: AsyncSession, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="Car", branch=branch)
    query = await NodeGetListQuery.init(
        session=session, branch=branch, schema=schema, filters={"owner__name__value": "John"}
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_and_sort(
    session: AsyncSession, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="Car", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        session=session,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_and_sort_with_revision(
    session: AsyncSession, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    node = await NodeManager.get_one(id=car_volt_main.id, session=session, branch=branch)
    node.is_electric.value = False
    await node.save(session=session)

    schema = registry.schema.get(name="Car", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        session=session,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(session=session)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_with_generics(session: AsyncSession, group_group1_main, branch: Branch):

    schema = registry.schema.get(name="Group", branch=branch)
    query = await NodeGetListQuery.init(
        session=session,
        branch=branch,
        schema=schema,
    )
    await query.execute(session=session)
    assert query.get_node_ids() == [group_group1_main.id]


async def test_query_NodeListGetInfoQuery(
    session: AsyncSession, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id]
    query = await NodeListGetInfoQuery.init(session=session, branch=branch, ids=ids)
    await query.execute(session=session)
    assert len(list(query.get_results_group_by(("n", "uuid")))) == 3


async def test_query_NodeListGetLocalAttributeValueQuery(
    session: AsyncSession, default_branch: Branch, car_person_schema
):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    car1 = await Node.init(session=session, schema="Car")
    await car1.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1)
    await car1.save(session=session)
    car2 = await Node.init(session=session, schema="Car")
    await car2.new(session=session, name="model3", nbr_seats=5, is_electric=True, owner=p1)
    await car2.save(session=session)

    ids = [
        car1.name.id,
        car1.nbr_seats.id,
        car1.is_electric.id,
        car1.color.id,
        car2.name.id,
        car2.nbr_seats.id,
        car2.is_electric.id,
        car2.color.id,
    ]

    query = await NodeListGetLocalAttributeValueQuery.init(
        session=session, ids=ids, branch=default_branch, at=Timestamp()
    )
    await query.execute(session=session)
    assert len(query.get_results_by_id()) == 8


async def test_query_NodeListGetAttributeQuery_all_fields(session: AsyncSession, base_dataset_02):
    default_branch = await get_branch(session=session, branch="main")
    branch1 = await get_branch(session=session, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 4 attributes per node(x2) = 8 attributes
    query = await NodeListGetAttributeQuery.init(session=session, ids=["c1", "c2", "c3"], branch=default_branch)
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(list(query.get_results())) == 8
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 4
    assert len(query.get_attributes_group_by_node()["c2"]["attrs"]) == 4

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 9 attributes because each node has 4 but c1at2 has a value both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(session=session, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(list(query.get_results())) == 11
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 4
    assert len(query.get_attributes_group_by_node()["c3"]["attrs"]) == 4


async def test_query_NodeListGetAttributeQuery_with_source(
    session, default_branch, criticality_schema, first_account, second_account
):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4, _source=first_account)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(
        session=session,
        name="medium",
        level={"value": 3, "source": second_account.id},
        description="My desc",
        color="#333333",
        _source=first_account,
    )
    await obj2.save(session=session)

    default_branch = await get_branch(session=session, branch="main")

    query = await NodeListGetAttributeQuery.init(
        session=session, ids=[obj1.id, obj2.id], branch=default_branch, include_source=True
    )
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == sorted([obj1.id, obj2.id])
    assert query.get_attributes_group_by_node()[obj1.id]["attrs"]["name"].source_uuid == first_account.id
    assert query.get_attributes_group_by_node()[obj2.id]["attrs"]["level"].source_uuid == second_account.id
    assert query.get_attributes_group_by_node()[obj2.id]["attrs"]["name"].source_uuid == first_account.id


async def test_query_NodeListGetAttributeQuery(session: AsyncSession, base_dataset_02):
    default_branch = await get_branch(session=session, branch="main")
    branch1 = await get_branch(session=session, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = await NodeListGetAttributeQuery.init(
        session=session, ids=["c1", "c2", "c3"], branch=default_branch, fields={"name": True, "is_electric": True}
    )
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 2
    assert len(query.get_attributes_group_by_node()["c2"]["attrs"]) == 2
    assert len(list(query.get_results())) == 4

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 5 attributes because each node has 1 but c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(
        session=session, ids=["c1", "c2", "c3"], branch=branch1, fields={"nbr_seats": True}
    )
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 1
    assert len(query.get_attributes_group_by_node()["c3"]["attrs"]) == 1
    assert len(list(query.get_results())) == 5

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 4 attributes because c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(
        session=session, ids=["c1"], branch=branch1, fields={"nbr_seats": True}
    )
    await query.execute(session=session)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(list(query.get_results())) == 4
    assert query.results[0].branch_score != query.results[1].branch_score


async def test_query_NodeListGetRelationshipsQuery(
    session: AsyncSession, default_branch: Branch, person_jack_tags_main
):
    default_branch = await get_branch(session=session, branch="main")
    query = await NodeListGetRelationshipsQuery.init(
        session=session,
        ids=[person_jack_tags_main.id],
        branch=default_branch,
    )
    await query.execute(session=session)
    result = query.get_peers_group_by_node()
    assert person_jack_tags_main.id in result
    assert "person__tag" in result[person_jack_tags_main.id]
    assert len(result[person_jack_tags_main.id]["person__tag"]) == 2
