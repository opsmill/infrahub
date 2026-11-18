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

    assert _rebase_keeps_branch_side(conflict_level=case.conflict_level, conflict=conflict) is case.expected
