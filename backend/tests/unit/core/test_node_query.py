from infrahub.core import get_branch
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeListGetAttributeQuery,
    NodeListGetLocalAttributeValueQuery,
)
from infrahub.core.timestamp import Timestamp


async def test_query_NodeListGetLocalAttributeValueQuery(session, default_branch, car_person_schema):
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


async def test_query_NodeListGetAttributeQuery_all_fields(session, base_dataset_02):
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


async def test_query_NodeListGetAttributeQuery(session, base_dataset_02):
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
