from unittest.mock import AsyncMock

import pytest
from infrahub_sdk.exceptions import TimestampFormatError
from pydantic import ValidationError as PydanticValidationError

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.relationship import Relationship
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import BranchNotFoundError, ValidationError


async def test_branch_name_validator(db: InfrahubDatabase) -> None:
    assert Branch(name="new-branch")
    assert Branch(name="cr1234")
    assert Branch(name="new.branch")
    assert Branch(name="new/branch")

    # Test path segment that ends with a period
    with pytest.raises(ValidationError):
        Branch(name="new/.")

    # Test two consecutive periods
    with pytest.raises(ValidationError):
        Branch(name="new..branch")

    # Test string starting with a forward slash
    with pytest.raises(ValidationError):
        Branch(name="/newbranch")

    # Test two consecutive forward slashes
    with pytest.raises(ValidationError):
        Branch(name="new//branch")

    # Test "@{"
    with pytest.raises(ValidationError):
        Branch(name="new@{branch")

    # Test backslash
    with pytest.raises(ValidationError):
        Branch(name="new\\branch")

    # Test ASCII control characters
    with pytest.raises(ValidationError):
        Branch(name="new\x01branch")

    # Test DEL character
    with pytest.raises(ValidationError):
        Branch(name="new\x7fbranch")

    # Test space character
    with pytest.raises(ValidationError):
        Branch(name="new branch")

    # Test tilde character
    with pytest.raises(ValidationError):
        Branch(name="new~branch")

    # Test caret character
    with pytest.raises(ValidationError):
        Branch(name="new^branch")

    # Test colon character
    with pytest.raises(ValidationError):
        Branch(name="new:branch")

    # Test question mark
    with pytest.raises(ValidationError):
        Branch(name="new?branch")

    # Test asterisk
    with pytest.raises(ValidationError):
        Branch(name="new*branch")

    # Test square bracket
    with pytest.raises(ValidationError):
        Branch(name="new[branch")

    # Test string ending with ".lock"
    with pytest.raises(ValidationError):
        Branch(name="newbranch.lock")

    # Test string ending with a forward slash
    with pytest.raises(ValidationError):
        Branch(name="newbranch/")

    # Test string ending with a period
    with pytest.raises(ValidationError):
        Branch(name="newbranch.")

    # Need at least 3 characters
    assert Branch(name="cr1")
    with pytest.raises(PydanticValidationError):
        Branch(name="cr")

    # No more than 250 characters
    with pytest.raises(PydanticValidationError):
        Branch(
            name="bklbvyzsqgllkryagisgpagqbisliossohumgqyebjcbrafdjgjzskbsmuxzloufibkhocxqxvpakmtecejwtcsuvfuskvapgaxlidutzaviwmymsxxskwqbgvrgvpkiuqyivccsbaqrwsitzvvzflchdzlvdqrjvfnfmybdbzkefwkhlctjuizwprvwoinsxxcwzjjcchbonasodsabrxdocloysizlfdgrclyfyamcaivkluskwrvunji"
        )

    assert Branch(name="new-branch")
    assert Branch(name="cr1234-qwerty-qwerty")


async def test_branch_branched_form_format_validator(db: InfrahubDatabase) -> None:
    assert Branch(name="new-branch").branched_from is not None

    time1 = Timestamp().to_string()
    assert Branch(name="cr1234", branched_from=time1).branched_from == time1

    with pytest.raises(TimestampFormatError):
        Branch(name="cr1234", branched_from="not a date")


async def test_get_query_filter_relationships_main(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    default_branch = await registry.get_branch(branch="main", db=db)

    filters, params = default_branch.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp(), include_outside_parentheses=False
    )

    expected_filters = [
        "(r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to > $time0)",
        "((r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to IS NULL)\n OR (r1.branch IN $branch0 AND r1.from <= $time0 AND r1.to > $time0))",
        "(r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to > $time0)",
        "((r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to IS NULL)\n OR (r2.branch IN $branch0 AND r2.from <= $time0 AND r2.to > $time0))",
    ]
    assert isinstance(filters, list)
    assert filters == expected_filters
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "time0"]


async def test_get_query_filter_relationships_branch1(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    branch1 = await registry.get_branch(branch="branch1", db=db)

    filters, params = branch1.get_query_filter_relationships(
        rel_labels=["r1", "r2"], at=Timestamp(), include_outside_parentheses=False
    )

    assert isinstance(filters, list)
    assert len(filters) == 4
    assert isinstance(params, dict)
    assert sorted(params.keys()) == ["branch0", "branch1", "time0", "time1"]


async def test_get_branches_and_times_to_query_main(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp("1s")

    main_branch = await registry.get_branch(branch="main", db=db)

    results = main_branch.get_branches_and_times_to_query(at=Timestamp())
    assert Timestamp(results[frozenset(["main"])]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query(at=t1)
    assert results[frozenset(["main"])] == t1.to_string()


async def test_get_branches_and_times_to_query_branch1(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp("1s")

    branch1 = await registry.get_branch(branch="branch1", db=db)

    t0 = Timestamp()
    results = branch1.get_branches_and_times_to_query(at=t0)
    assert Timestamp(results[frozenset(["branch1"])]) > now
    assert results[frozenset(["main"])] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query(at=t1)
    assert results[frozenset(["branch1"])] == t1.to_string()
    assert results[frozenset(["main"])] == base_dataset_02["time_m45"]


async def test_get_branches_and_times_to_query_global_main(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp("1s")

    main_branch = await registry.get_branch(branch="main", db=db)

    results = main_branch.get_branches_and_times_to_query_global(at=Timestamp())
    assert Timestamp(results[frozenset((GLOBAL_BRANCH_NAME, "main"))]) > now

    t1 = Timestamp("2s")
    results = main_branch.get_branches_and_times_to_query_global(at=t1)
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == t1.to_string()


async def test_get_branches_and_times_to_query_global_branch1(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp("1s")

    branch1 = await registry.get_branch(branch="branch1", db=db)

    t0 = Timestamp()
    results = branch1.get_branches_and_times_to_query_global(at=t0)
    assert Timestamp(results[frozenset((GLOBAL_BRANCH_NAME, "branch1"))]) > now
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    results = branch1.get_branches_and_times_to_query_global(at=t1)
    assert results[frozenset((GLOBAL_BRANCH_NAME, "branch1"))] == t1.to_string()
    assert results[frozenset((GLOBAL_BRANCH_NAME, "main"))] == base_dataset_02["time_m45"]


async def test_get_branches_and_times_for_range_main(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp()
    main_branch = await registry.get_branch(branch="main", db=db)

    start_times, end_times = main_branch.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert list(start_times.keys()) == ["main"]
    assert list(end_times.keys()) == ["main"]
    assert start_times["main"] == main_branch.created_at
    assert end_times["main"] == now.to_string()

    t1 = Timestamp("2s")
    t5 = Timestamp("5s")
    start_times, end_times = main_branch.get_branches_and_times_for_range(start_time=t5, end_time=t1)
    assert list(start_times.keys()) == ["main"]
    assert list(end_times.keys()) == ["main"]
    assert start_times["main"] == t5.to_string()
    assert end_times["main"] == t1.to_string()


async def test_get_branches_and_times_for_range_branch1(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    now = Timestamp()
    branch1 = await registry.get_branch(branch="branch1", db=db)

    start_times, end_times = branch1.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert sorted(start_times.keys()) == ["branch1", "main"]
    assert sorted(end_times.keys()) == ["branch1", "main"]
    assert end_times["branch1"] == now.to_string()
    assert end_times["main"] == now.to_string()
    assert start_times["branch1"] == base_dataset_02["time_m45"]
    assert start_times["main"] == base_dataset_02["time_m45"]

    t1 = Timestamp("2s")
    t10 = Timestamp("10s")
    start_times, end_times = branch1.get_branches_and_times_for_range(start_time=t10, end_time=t1)
    assert sorted(start_times.keys()) == ["branch1", "main"]
    assert sorted(end_times.keys()) == ["branch1", "main"]
    assert end_times["branch1"] == t1.to_string()
    assert end_times["main"] == t1.to_string()
    assert start_times["branch1"] == t10.to_string()
    assert start_times["main"] == t10.to_string()


async def test_get_branches_and_times_for_range_branch2(db: InfrahubDatabase, base_dataset_03: dict) -> None:
    now = Timestamp()
    branch2 = await registry.get_branch(branch="branch2", db=db)

    start_times, end_times = branch2.get_branches_and_times_for_range(start_time=Timestamp("1h"), end_time=now)
    assert sorted(start_times.keys()) == ["branch2", "main"]
    assert sorted(end_times.keys()) == ["branch2", "main"]
    assert end_times["branch2"] == now.to_string()
    assert end_times["main"] == now.to_string()
    assert start_times["branch2"] == base_dataset_03["time_m90"]
    assert start_times["main"] == base_dataset_03["time_m30"]

    t1 = Timestamp("2s")
    t10 = Timestamp("10s")
    start_times, end_times = branch2.get_branches_and_times_for_range(start_time=t10, end_time=t1)
    assert sorted(start_times.keys()) == ["branch2", "main"]
    assert sorted(end_times.keys()) == ["branch2", "main"]
    assert end_times["branch2"] == t1.to_string()
    assert end_times["main"] == t1.to_string()
    assert start_times["branch2"] == t10.to_string()
    assert start_times["main"] == t10.to_string()


async def test_is_isolated(db: InfrahubDatabase, base_dataset_02: dict) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    branch1.is_isolated = True
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, db=db), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].name.value == "accord"

    branch1.is_isolated = False
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, db=db), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].name.value == "volt"


async def test_delete_branch(
    db: InfrahubDatabase, default_branch: Branch, repos_in_main: dict, car_person_schema: SchemaBranch
) -> None:
    branch_name = "delete-me"
    branch = await create_branch(branch_name=branch_name, db=db)
    found = await Branch.get_by_name(name=branch_name, db=db)

    p1 = await Node.init(schema="TestPerson", branch=branch_name, db=db)
    await p1.new(name="Bobby", height=175, db=db)
    await p1.save(db=db)

    relationship_query = """
    MATCH ()-[r]-()
    WHERE r.branch = $branch_name
    RETURN r
    """
    params = {"branch_name": branch_name}
    pre_delete = await db.execute_query(query=relationship_query, params=params)

    await branch.delete(db=db)
    post_delete = await db.execute_query(query=relationship_query, params=params)

    assert branch.id == found.id
    with pytest.raises(BranchNotFoundError):
        await Branch.get_by_name(name=branch_name, db=db)

    assert pre_delete
    assert not post_delete


async def test_delete_branch_with_agnostic_attrs_and_rels(
    db: InfrahubDatabase,
    default_branch: Branch,
    repos_in_main: dict,
    branch_aware_node_with_agnostic_attrs_schema: SchemaBranch,
) -> None:
    """Test that branch deletion properly removes branch-aware Nodes with branch-agnostic attributes and relationships.

    When a branch-aware Node is created on a branch:
    - The Node itself is connected to Root with branch-specific IS_PART_OF edge
    - Branch-agnostic attributes have HAS_ATTRIBUTE/HAS_VALUE edges with branch="__global__"
    - Branch-agnostic relationships have IS_RELATED edges with branch="__global__"

    When the branch is deleted, ALL of these should be removed:
    - The Node vertex
    - The Attribute vertices and their values
    - The Relationship vertices
    """
    branch_name = "delete-me-agnostic"
    branch = await create_branch(branch_name=branch_name, db=db)

    # Create a Site on main branch that we'll reference
    site = await Node.init(schema="TestSite", branch=default_branch, db=db)
    await site.new(name="SiteA", db=db)
    await site.save(db=db)

    # Create a Device on the branch with branch-agnostic attribute and relationship
    device = await Node.init(schema="TestDevice", branch=branch_name, db=db)
    await device.new(name="Device1", serial_number="SN-12345", site=site, db=db)
    await device.save(db=db)

    device_uuid = device.id
    attr_uuid = device.get_attribute("serial_number").id
    agnostic_rel = await device.get_relationship("site").get_relationship(db=db, peer_id=site.id)
    rel_uuid = agnostic_rel.id

    # Delete the branch
    await branch.delete(db=db)

    # Verify the branch is deleted
    with pytest.raises(BranchNotFoundError):
        await Branch.get_by_name(name=branch_name, db=db)

    # Verify the Node vertex is deleted using its UUID
    vertices_exist_query = """
    MATCH (n:Node|Attribute|Relationship)
    WHERE n.uuid IN $uuids
    RETURN count(n) AS count
    """
    node_result = await db.execute_query(
        query=vertices_exist_query, params={"uuids": [device_uuid, attr_uuid, rel_uuid]}
    )
    assert node_result[0]["count"] == 0, "Node vertex should be deleted after branch deletion"


async def test_delete_branch_after_merge_preserves_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    repos_in_main: dict,
    branch_aware_node_with_agnostic_attrs_schema: SchemaBranch,
) -> None:
    """Test that branch deletion after merge preserves nodes that were merged to the default branch.

    When a branch-aware Node with branch-agnostic attributes/relationships is:
    1. Created on a branch
    2. Merged to the default branch
    3. Then the branch is deleted

    The Node should still be retrievable on the default branch because it now exists there.
    """
    branch_name = "merge-then-delete"
    branch = await create_branch(branch_name=branch_name, db=db)

    # Create a Site on main branch that we'll reference
    site = await Node.init(schema="TestSite", branch=default_branch, db=db)
    await site.new(name="SiteB", db=db)
    await site.save(db=db)

    # Create a Device on the branch with branch-agnostic attribute and relationship
    device = await Node.init(schema="TestDevice", branch=branch_name, db=db)
    await device.new(name="Device2", serial_number="SN-67890", site=site, db=db)
    await device.save(db=db)

    # Merge the branch to default
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    merge_at = Timestamp()
    await diff_merger.merge_graph(at=merge_at)

    # Verify the device exists on main after merge
    device_on_main = await NodeManager.get_one(db=db, branch=default_branch, id=device.id)
    assert device_on_main is not None, "Device should exist on main branch after merge"
    assert device_on_main.get_attribute("name").value == "Device2"
    assert device_on_main.get_attribute("serial_number").value == "SN-67890"

    # Delete the branch
    await branch.delete(db=db)

    # Verify the branch is deleted
    with pytest.raises(BranchNotFoundError):
        await Branch.get_by_name(name=branch_name, db=db)

    # Verify the device is STILL retrievable on the default branch
    device_after_branch_delete = await NodeManager.get_one(db=db, branch=default_branch, id=device.id)
    assert device_after_branch_delete is not None, "Device should still exist on main branch after branch deletion"
    assert device_after_branch_delete.get_attribute("name").value == "Device2"
    assert device_after_branch_delete.get_attribute("serial_number").value == "SN-67890"

    # Verify the relationship is still intact
    site_rel = await device_after_branch_delete.get_relationship("site").get(db=db)
    assert site_rel is not None, "Site relationship should still exist after branch deletion"
    assert isinstance(site_rel, Relationship)
    assert site_rel.get_peer_id() == site.id


async def test_create_branch(db: InfrahubDatabase, empty_database: None) -> None:
    """Validate that creating a branch with quotes in descriptions work and are properly handled with params"""
    branch_name = "branching-out"
    description = "It's supported with quotes"
    await create_branch(branch_name=branch_name, db=db, description=description)
    branch = await Branch.get_by_name(name=branch_name, db=db)
    assert branch.name == branch_name
    assert branch.description == description
