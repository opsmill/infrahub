"""Diff calculator coverage for the AGNOSTIC node + AWARE attribute scenario.

Mirrors the real CoreReadOnlyRepository schema shape (AGNOSTIC node with
AWARE ref/commit attributes). The node exists on default before the branch
is created; the AWARE attribute is updated on the branch; the diff must
capture the attribute change against the original value on default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from tests.component.core.diff.conftest import REPO_MIRROR_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_diff_aware_attribute_update_on_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, repo_mirror_main: Node
) -> None:
    """Update an AWARE attribute on an AGNOSTIC node on a branch, then verify
    that the diff captures both the previous (default) and new (branch) values
    for that attribute."""
    branch = await create_branch(db=db, branch_name="repo_mirror_branch")
    from_time = Timestamp(branch.created_at)

    repo_on_branch = await NodeManager.get_one(db=db, branch=branch, id=repo_mirror_main.id)
    new_commit = "b" * 40
    repo_on_branch.get_attribute("commit").value = new_commit
    repo_on_branch.get_attribute("ref").value = "feature"
    await repo_on_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == repo_mirror_main.id
    assert node_diff.kind == REPO_MIRROR_KIND
    assert node_diff.action is DiffAction.UPDATED

    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"commit", "ref"}, (
        "AWARE attribute updates on an AGNOSTIC node should be captured by the diff; "
        f"got attributes: {set(attributes_by_name.keys())}"
    )

    commit_diff = attributes_by_name["commit"]
    assert commit_diff.action is DiffAction.UPDATED
    commit_props = {prop.property_type: prop for prop in commit_diff.properties}
    assert DatabaseEdgeType.HAS_VALUE in commit_props
    commit_value_prop = commit_props[DatabaseEdgeType.HAS_VALUE]
    assert commit_value_prop.action is DiffAction.UPDATED
    assert commit_value_prop.previous_value == "a" * 40
    assert commit_value_prop.new_value == new_commit

    ref_diff = attributes_by_name["ref"]
    assert ref_diff.action is DiffAction.UPDATED
    ref_props = {prop.property_type: prop for prop in ref_diff.properties}
    ref_value_prop = ref_props[DatabaseEdgeType.HAS_VALUE]
    assert ref_value_prop.action is DiffAction.UPDATED
    assert ref_value_prop.previous_value == "main"
    assert ref_value_prop.new_value == "feature"
