from infrahub.core import get_branch
from infrahub.core.query.diff import (
    DiffNodePropertiesByIDSRangeQuery,
    DiffNodeQuery,
    DiffRelationshipPropertiesByIDSRangeQuery,
)


async def test_diff_node_query(session, default_branch, base_dataset_02):
    branch1 = await get_branch(branch="branch1", session=session)

    # Query all nodes from the creation of the first nodes (m60) to now
    query = await DiffNodeQuery.init(
        session=session,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 6

    # Query all nodes from m30 to now
    query = await DiffNodeQuery.init(
        session=session,
        branch=branch1,
        diff_from=base_dataset_02["time_m30"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 1

    # Query all nodes from m60 to m30
    query = await DiffNodeQuery.init(
        session=session,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m30"],
    )
    await query.execute(session=session)

    assert len(query.results) == 5


async def test_diff_node_properties_ids_range_query(session, default_branch, base_dataset_02):
    branch1 = await get_branch(branch="branch1", session=session)

    # Query all Nodes from the creation of the first nodes (m60) to now
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 24

    c1at1_result = query.get_results_by_id_and_prop_type(attr_id="c1at1", prop_type="HAS_VALUE")
    assert len(c1at1_result) == 2
    assert c1at1_result[0].get("ap").get("value") == "accord"
    assert c1at1_result[1].get("ap").get("value") == "volt"

    # Query all nodes from m25 to now
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m25"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 13

    # Query all nodes from m60 to m25
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m25"],
    )
    await query.execute(session=session)

    assert len(query.results) == 12


async def test_diff_relationship_properties_ids_range_query(session, default_branch, base_dataset_02):
    branch1 = await get_branch(branch="branch1", session=session)

    # Query all Rels from the creation of the first nodes (m60) to now
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 6

    r1_result = query.get_results_by_id_and_prop_type(rel_id="r1", prop_type="IS_PROTECTED")

    assert len(r1_result) == 2

    # Query all nodes from m25 to now
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m25"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 3

    # Query all nodes from m60 to m25
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m25"],
    )
    await query.execute(session=session)

    assert len(query.results) == 3
