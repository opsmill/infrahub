from collections import defaultdict

from infrahub.core.query.diff import (
    DiffAttributeQuery,
    DiffNodePropertiesByIDSRangeQuery,
    DiffNodeQuery,
    DiffRelationshipPropertiesByIDSRangeQuery,
    DiffRelationshipPropertyQuery,
    DiffRelationshipQuery,
)
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


def group_results_per_node(results):
    results_per_node = defaultdict(list)
    for result in results:
        results_per_node[result.get("n").get("uuid")].append(result)

    return results_per_node


async def test_diff_node_query(db: InfrahubDatabase, default_branch, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Query all nodes from the creation of the first nodes (m60) to now
    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)
    assert len(query.results) == 6

    # Query all nodes from m30 to now
    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m30"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)
    assert len(query.results) == 1

    # Query all nodes from m60 to m30
    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m30"],
    )
    await query.execute(db=db)

    assert len(query.results) == 5

    # Filter node by NAMESPACES
    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_include=["NotPresent"],
    )
    await query.execute(db=db)
    assert len(query.results) == 0

    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_include=["Test", "Other"],
    )
    await query.execute(db=db)
    assert len(query.results) == 6

    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_exclude=["Other"],
    )
    await query.execute(db=db)
    assert len(query.results) == 6

    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_exclude=["Test"],
    )
    await query.execute(db=db)
    assert len(query.results) == 0

    # Filter node by KINDS
    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_include=["TestCar"],
    )
    await query.execute(db=db)
    assert len(query.results) == 3

    query = await DiffNodeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_exclude=["TestCar"],
    )
    await query.execute(db=db)
    assert len(query.results) == 3


async def test_diff_attribute_query(db: InfrahubDatabase, default_branch, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Query all attributes from the creation of the branch (m45) to now
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m45"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    results_per_node = group_results_per_node(query.results)

    assert sorted(results_per_node.keys()) == ["c1", "c2", "c3"]

    assert len(results_per_node["c1"]) == 3
    assert len(results_per_node["c2"]) == 12
    assert len(results_per_node["c3"]) == 12

    # Query all attributes from m30 to now
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m30"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    results_per_node = group_results_per_node(query.results)
    assert sorted(results_per_node.keys()) == ["c1", "c2"]

    assert len(results_per_node["c1"]) == 3
    assert len(results_per_node["c2"]) == 12

    # Query all nodes from m45 to m30
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m45"],
        diff_to=base_dataset_02["time_m30"],
    )
    await query.execute(db=db)

    results_per_node = group_results_per_node(query.results)
    assert sorted(results_per_node.keys()) == ["c3"]

    assert len(results_per_node["c3"]) == 12

    # Filter node by NAMESPACE
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_include=["Test"],
    )
    await query.execute(db=db)
    results_per_node = group_results_per_node(query.results)
    assert sorted(results_per_node.keys()) == ["c1", "c2", "c3"]

    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_exclude=["Test", "Other"],
    )
    await query.execute(db=db)
    assert len(query.results) == 0

    # Filter node by KINDS
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_include=["TestPerson"],
    )
    await query.execute(db=db)
    assert len(query.results) == 0

    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_exclude=["TestPerson"],
    )
    await query.execute(db=db)
    results_per_node = group_results_per_node(query.results)
    assert sorted(results_per_node.keys()) == ["c1", "c2", "c3"]


async def test_diff_attribute_query_rebased_branch(db: InfrahubDatabase, default_branch, base_dataset_03):
    branch2 = await registry.get_branch(branch="branch2", db=db)

    # Query all attributes from the creation of the branch (m45) to now
    query = await DiffAttributeQuery.init(
        db=db,
        branch=branch2,
    )
    await query.execute(db=db)

    results_per_node = group_results_per_node(query.results)
    assert sorted(results_per_node.keys()) == ["p2"]

    assert len(results_per_node["p2"]) == 2


async def test_diff_node_properties_ids_range_query(db: InfrahubDatabase, default_branch, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Query all Nodes from the creation of the first nodes (m60) to now
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    assert len(query.results) == 24

    c1at1_result = query.get_results_by_id_and_prop_type(attr_id="c1at1", prop_type="HAS_VALUE")
    assert len(c1at1_result) == 2
    assert c1at1_result[0].get("ap").get("value") == "accord"
    assert c1at1_result[1].get("ap").get("value") == "volt"

    # Query all nodes from m25 to now
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m25"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    assert len(query.results) == 24

    # Query all nodes from m60 to m25
    query = await DiffNodePropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["c1at1", "c1at2", "c1at3", "c1at4", "c2at1", "c2at2", "2at3", "c2at4"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m25"],
    )
    await query.execute(db=db)

    assert len(query.results) == 12


async def test_diff_relationship_properties_ids_range_query(db: InfrahubDatabase, default_branch, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Query all Rels from the creation of the first nodes (m60) to now
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    assert len(query.results) == 6

    r1_result = query.get_results_by_id_and_prop_type(rel_id="r1", prop_type="IS_PROTECTED")

    assert len(r1_result) == 2

    # Query all nodes from m25 to now
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m25"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(db=db)

    assert len(query.results) == 6

    # Query all nodes from m60 to m25
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        db=db,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time_m25"],
    )
    await query.execute(db=db)

    assert len(query.results) == 3


async def test_DiffRelationshipQuery(db: InfrahubDatabase, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Execute the query with default timestamp from the creation of the branch to now
    query = await DiffRelationshipQuery.init(db=db, branch=branch1)
    await query.execute(db=db)
    assert query.diff_from == Timestamp(base_dataset_02["time_m45"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff since time0
    query = await DiffRelationshipQuery.init(db=db, branch=branch1, diff_from=Timestamp(base_dataset_02["time0"]))
    await query.execute(db=db)
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0

    # FILTERS by KINDS
    query = await DiffRelationshipQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_exclude=["TestPerson"],
    )
    await query.execute(db=db)
    results = list(query.get_results())
    assert len(results) == 0

    query = await DiffRelationshipQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        kinds_include=["TestPerson"],
    )
    await query.execute(db=db)
    results = list(query.get_results())
    assert len(results) == 2

    # FILTERS by NAMESPACE
    query = await DiffRelationshipQuery.init(
        db=db,
        branch=branch1,
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
        namespaces_include=["Test"],
    )
    await query.execute(db=db)
    results = list(query.get_results())
    assert len(results) == 2


async def test_DiffRelationshipPropertyQuery(db: InfrahubDatabase, base_dataset_02):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Execute the query with default timestamp from the creation of the branch to now
    # 4 changes are expected
    query = await DiffRelationshipPropertyQuery.init(db=db, branch=branch1)
    await query.execute(db=db)
    assert query.diff_from == Timestamp(base_dataset_02["time_m45"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 4

    # Execute the query to calculate the diff since time0
    # No change are expected
    query = await DiffRelationshipPropertyQuery.init(
        db=db, branch=branch1, diff_from=Timestamp(base_dataset_02["time0"])
    )
    await query.execute(db=db)
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0

    # Execute the query to calculate the diff between time_m35 and time_m25
    # Only 1 change is expected r1/IS_PROTECTED at m30
    query = await DiffRelationshipPropertyQuery.init(
        db=db,
        branch=branch1,
        diff_from=Timestamp(base_dataset_02["time_m35"]),
        diff_to=Timestamp(base_dataset_02["time_m25"]),
    )
    await query.execute(db=db)
    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff between time_m25 and time_m10
    # Only 3 changes is expected : creation of r2 at m20 and modification of r1/IS_VISIBLE
    query = await DiffRelationshipPropertyQuery.init(
        db=db,
        branch=branch1,
        diff_from=Timestamp(base_dataset_02["time_m25"]),
        diff_to=Timestamp(base_dataset_02["time_m10"]),
    )
    await query.execute(db=db)
    results = list(query.get_results())
    assert len(results) == 3


async def test_DiffRelationshipPropertyQuery_both_branches(db: InfrahubDatabase, base_dataset_04):
    branch1 = await registry.get_branch(branch="branch1", db=db)

    # Execute the query with default timestamp from the creation of the branch to now
    # 4 changes are expected
    query = await DiffRelationshipPropertyQuery.init(
        db=db,
        branch=branch1,
        diff_from=Timestamp(base_dataset_04["time_m20"]),
        diff_to=Timestamp(base_dataset_04["time0"]),
    )
    await query.execute(db=db)

    results = list(query.get_results())
    assert len(results) == 4
