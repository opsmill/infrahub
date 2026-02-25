from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetListByAttributeValueQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_query_NodeGetListByAttributeValueQuery_partial_match(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    person_alfred_main: Node,
    branch: Branch,
) -> None:
    """Test partial match search finds nodes containing the search value."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="John",
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 1
    assert results[0].uuid == person_john_main.id
    assert results[0].kind == "TestPerson"


async def test_query_NodeGetListByAttributeValueQuery_partial_match_multiple_results(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    person_alfred_main: Node,
    branch: Branch,
) -> None:
    """Test partial match search finds multiple nodes when search value matches multiple names."""
    # Both Albert and Alfred start with "Al"
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="Al",
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 2
    result_uuids = {r.uuid for r in results}
    assert result_uuids == {person_albert_main.id, person_alfred_main.id}


async def test_query_NodeGetListByAttributeValueQuery_exact_match(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    person_alfred_main: Node,
    branch: Branch,
) -> None:
    """Test exact match search only finds nodes with exact value."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="John",
        partial_match=False,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 1
    assert results[0].uuid == person_john_main.id


async def test_query_NodeGetListByAttributeValueQuery_exact_match_no_partial(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    person_alfred_main: Node,
    branch: Branch,
) -> None:
    """Test exact match search does not find partial matches."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="Al",
        partial_match=False,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 0


async def test_query_NodeGetListByAttributeValueQuery_case_insensitive(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
) -> None:
    """Test search is case-insensitive when case_insensitive=True."""
    # Search with lowercase
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="john",
        partial_match=True,
        case_insensitive=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 1
    assert results[0].uuid == person_john_main.id

    # Search with uppercase
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="JOHN",
        partial_match=True,
        case_insensitive=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 1
    assert results[0].uuid == person_john_main.id


async def test_query_NodeGetListByAttributeValueQuery_filter_by_kind(
    db: InfrahubDatabase,
    person_john_main: Node,
    car_accord_main: Node,
    car_volt_main: Node,
    branch: Branch,
) -> None:
    """Test filtering results by node kind."""
    # Search for 'o' which exists in both 'John' and 'accord'/'volt'
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="o",
        kinds=["TestPerson"],
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    # Should only return person nodes, not cars
    result_uuids = {r.uuid for r in results}
    assert person_john_main.id in result_uuids
    # Cars should be excluded even though they have 'o' in their name
    assert car_accord_main.id not in result_uuids
    assert car_volt_main.id not in result_uuids


async def test_query_NodeGetListByAttributeValueQuery_filter_by_multiple_kinds(
    db: InfrahubDatabase,
    person_john_main: Node,
    car_accord_main: Node,
    branch: Branch,
) -> None:
    """Test filtering results by multiple node kinds."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="o",
        kinds=["TestPerson", "TestCar"],
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    result_uuids = {r.uuid for r in results}
    # Should include both person and car nodes
    assert person_john_main.id in result_uuids
    assert car_accord_main.id in result_uuids


async def test_query_NodeGetListByAttributeValueQuery_no_results(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
) -> None:
    """Test search returns no results when no match found."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="nonexistent",
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 0


async def test_query_NodeGetListByAttributeValueQuery_deleted_node(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
) -> None:
    """Test deleted nodes are not returned in search results."""
    # Delete John
    node_to_delete = await NodeManager.get_one(id=person_john_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)

    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="John",
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 0


async def test_query_NodeGetListByAttributeValueQuery_get_node_ids_method(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
) -> None:
    """Test get_data returns proper result dataclass with uuid and kind."""
    query = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch,
        search_value="J",
        partial_match=True,
    )
    await query.execute(db=db)
    results = list(query.get_data())
    assert len(results) == 2
    for result in results:
        assert result.uuid in [person_john_main.id, person_jim_main.id]
        assert result.kind == "TestPerson"


async def test_query_NodeGetListByAttributeValueQuery_branch_aware(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """Test search respects branch boundaries for branch-aware nodes."""
    # Create person on main branch
    person_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_main.new(db=db, name="MainOnlyPerson", height=175)
    await person_main.save(db=db)

    # Create a new branch
    branch2 = await create_branch(branch_name="branch_for_search_test", db=db)

    # Create person only on branch2
    person_branch = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await person_branch.new(db=db, name="BranchOnlyPerson", height=165)
    await person_branch.save(db=db)

    # Search on main branch should find MainOnlyPerson but not BranchOnlyPerson
    query_main = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=default_branch,
        search_value="OnlyPerson",
        partial_match=True,
    )
    await query_main.execute(db=db)
    results_main = list(query_main.get_data())
    result_uuids_main = {r.uuid for r in results_main}
    assert person_main.id in result_uuids_main
    assert person_branch.id not in result_uuids_main

    # Search on branch2 should find both (inherited from main + branch-specific)
    query_branch = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch2,
        search_value="OnlyPerson",
        partial_match=True,
    )
    await query_branch.execute(db=db)
    results_branch = list(query_branch.get_data())
    result_uuids_branch = {r.uuid for r in results_branch}
    assert person_main.id in result_uuids_branch
    assert person_branch.id in result_uuids_branch


async def test_query_NodeGetListByAttributeValueQuery_updated_attribute_in_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """Test search finds updated attribute values in branches."""
    # Create person on main branch
    person_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_main.new(db=db, name="OriginalName", height=175)
    await person_main.save(db=db)

    # Create a new branch
    branch2 = await create_branch(branch_name="branch_for_update_test", db=db)

    # Update name in branch
    person_in_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_main.id)
    person_in_branch.name.value = "UpdatedName"
    await person_in_branch.save(db=db)

    # Search on main should find OriginalName
    query_main = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=default_branch,
        search_value="OriginalName",
        partial_match=True,
    )
    await query_main.execute(db=db)
    results_main = list(query_main.get_data())
    assert len(results_main) == 1
    assert results_main[0].uuid == person_main.id

    # Search on main should NOT find UpdatedName
    query_main_updated = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=default_branch,
        search_value="UpdatedName",
        partial_match=True,
    )
    await query_main_updated.execute(db=db)
    results_main_updated = list(query_main_updated.get_data())
    assert len(results_main_updated) == 0

    # Search on branch should find UpdatedName
    query_branch = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch2,
        search_value="UpdatedName",
        partial_match=True,
    )
    await query_branch.execute(db=db)
    results_branch = list(query_branch.get_data())
    assert len(results_branch) == 1
    assert results_branch[0].uuid == person_main.id


async def test_query_NodeGetListByAttributeValueQuery_deleted_in_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """Test deleted nodes in branch are not returned in branch search but still appear in main."""
    # Create person on main branch
    person_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_main.new(db=db, name="PersonToDelete", height=175)
    await person_main.save(db=db)

    # Create a new branch
    branch2 = await create_branch(branch_name="branch_for_delete_test", db=db)

    # Delete in branch
    person_in_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_main.id)
    await person_in_branch.delete(db=db)

    # Search on main should still find the person
    query_main = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=default_branch,
        search_value="PersonToDelete",
        partial_match=True,
    )
    await query_main.execute(db=db)
    results_main = list(query_main.get_data())
    assert len(results_main) == 1
    assert results_main[0].uuid == person_main.id

    # Search on branch should NOT find the deleted person
    query_branch = await NodeGetListByAttributeValueQuery.init(
        db=db,
        branch=branch2,
        search_value="PersonToDelete",
        partial_match=True,
    )
    await query_branch.execute(db=db)
    results_branch = list(query_branch.get_data())
    assert len(results_branch) == 0
