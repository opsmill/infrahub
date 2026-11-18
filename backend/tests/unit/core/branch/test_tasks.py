from dataclasses import dataclass

import pytest

from infrahub.core.branch.tasks import _rebase_keeps_branch_side
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import ConflictLevel, EnrichedDiffConflict


@dataclass
class RebaseKeepsBranchSideCase:
    name: str
    conflict_level: ConflictLevel
    base_branch_action: DiffAction
    expected: bool
    conflict_path: str = "data/node-id/name/value"


REBASE_KEEPS_BRANCH_SIDE_CASES = [
    RebaseKeepsBranchSideCase(
        name="attribute_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=True,
    ),
    RebaseKeepsBranchSideCase(
        name="attribute_removed_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.REMOVED,
        expected=False,
    ),
    RebaseKeepsBranchSideCase(
        name="owners_of_a_node_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
        conflict_path="data/node-id/node_metadata__owners/property/HAS_OWNER",
    ),
    RebaseKeepsBranchSideCase(
        name="sources_of_a_node_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
        conflict_path="data/node-id/node_metadata__sources/property/HAS_SOURCE",
    ),
    RebaseKeepsBranchSideCase(
        name="source_of_an_attribute_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=True,
        conflict_path="data/node-id/name/property/HAS_SOURCE",
    ),
    RebaseKeepsBranchSideCase(
        name="owners_that_a_profile_gives_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
        conflict_path="data/node-id/node_metadata__target_owners/property/HAS_OWNER",
    ),
    RebaseKeepsBranchSideCase(
        name="owners_of_an_attribute_updated_on_the_default_branch",
        conflict_level=ConflictLevel.ATTRIBUTE_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
        conflict_path="data/node-id/name/property/HAS_OWNER",
    ),
    RebaseKeepsBranchSideCase(
        name="relationship_property_updated_on_the_default_branch",
        conflict_level=ConflictLevel.RELATIONSHIP_PROPERTY,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
    ),
    RebaseKeepsBranchSideCase(
        name="cardinality_one_peer",
        conflict_level=ConflictLevel.RELATIONSHIP_ELEMENT,
        base_branch_action=DiffAction.UPDATED,
        expected=False,
    ),
    RebaseKeepsBranchSideCase(
        name="node",
        conflict_level=ConflictLevel.NODE,
        base_branch_action=DiffAction.REMOVED,
        expected=False,
    ),
]


@pytest.mark.parametrize("case", REBASE_KEEPS_BRANCH_SIDE_CASES, ids=lambda case: case.name)
def test_rebase_keeps_branch_side(case: RebaseKeepsBranchSideCase) -> None:
    conflict = EnrichedDiffConflict(
        uuid="conflict",
        base_branch_action=case.base_branch_action,
        base_branch_value=None,
        diff_branch_action=DiffAction.UPDATED,
        diff_branch_value="branch-value",
    )

    assert (
        _rebase_keeps_branch_side(
            conflict_path=case.conflict_path, conflict_level=case.conflict_level, conflict=conflict
        )
        is case.expected
    )
