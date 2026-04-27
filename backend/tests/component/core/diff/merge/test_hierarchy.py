"""Hierarchical ancestor/descendant relationships survive merge."""

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions, RelationshipHierarchyDirection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.conftest import _build_hierarchical_location_data
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_hierarchy_preserved(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    branch_name = "branch_hierarch"
    branch = await create_branch(db=db, branch_name=branch_name)
    hierarchy_data = await _build_hierarchical_location_data(db=db, branch=branch)

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=at)

    region_schema = registry.schema.get(name="LocationRegion", duplicate=False)
    region = hierarchy_data["europe"]
    region_descendants = [
        hierarchy_data["paris"],
        hierarchy_data["paris-r1"],
        hierarchy_data["paris-r2"],
        hierarchy_data["london"],
        hierarchy_data["london-r1"],
        hierarchy_data["london-r2"],
    ]
    site_schema = registry.schema.get(name="LocationSite", duplicate=False)
    site = hierarchy_data["paris-r2"]
    site_ancestors = [
        hierarchy_data["paris"],
        hierarchy_data["europe"],
    ]

    retrieved_descendants_map = await NodeManager.query_hierarchy(
        db=db,
        branch=default_branch,
        id=region.id,
        node_schema=region_schema,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        filters={},
    )
    assert set(retrieved_descendants_map.keys()) == {d.id for d in region_descendants}
    retrieved_ancestors_map = await NodeManager.query_hierarchy(
        db=db,
        branch=default_branch,
        id=site.id,
        node_schema=site_schema,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        filters={},
    )
    assert set(retrieved_ancestors_map.keys()) == {d.id for d in site_ancestors}

    # Validate metadata on merged nodes - europe region was created on branch and merged
    europe_with_metadata = await NodeManager.get_one(
        db=db, id=region.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    # Merged nodes should have updated_at set to merge time
    assert europe_with_metadata._get_updated_at() == at

    await verify_graph(db=db)


async def test_hierarchy_parent_change_on_branch_after_merge(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    """After merging a branch that changes a node's parent, the hierarchy query on the
    default branch should only return the new parent.
    """
    # Create hierarchy data on the default branch: europe -> paris, north-america -> seattle
    hierarchy_data = await _build_hierarchical_location_data(db=db, branch=default_branch)
    europe = hierarchy_data["europe"]
    north_america = hierarchy_data["north-america"]
    paris = hierarchy_data["paris"]

    # Verify initial state: paris has parent europe
    site_schema = paris.get_schema()
    ancestors_map = await NodeManager.query_hierarchy(
        db=db,
        branch=default_branch,
        id=paris.id,
        node_schema=site_schema,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        filters={},
    )
    assert set(ancestors_map.keys()) == {europe.id}

    # Create a branch and change paris's parent from europe to north-america
    branch = await create_branch(db=db, branch_name="change-parent")
    paris_on_branch = await NodeManager.get_one(db=db, branch=branch, id=paris.id)
    await paris_on_branch.get_relationship("parent").update(db=db, data=north_america)
    await paris_on_branch.save(db=db)

    # Merge the branch back to the default branch
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    # After merge, query ancestors of paris on the default branch.
    # It should only have north-america as parent, NOT both europe and north-america.
    ancestors_after_merge = await NodeManager.query_hierarchy(
        db=db,
        branch=default_branch,
        id=paris.id,
        node_schema=site_schema,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        filters={},
    )
    assert set(ancestors_after_merge.keys()) == {north_america.id}, (
        f"Expected only north-america ({north_america.id}) as ancestor of paris after merge, "
        f"but got: {set(ancestors_after_merge.keys())}. "
        f"europe ({europe.id}) should no longer be an ancestor."
    )
