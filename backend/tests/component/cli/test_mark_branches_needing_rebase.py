from infrahub.cli.db import mark_branches_needing_rebase
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase


async def test_mark_branches_needing_rebase_skips_terminal_branches(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    open_branch = await create_branch(branch_name="open-branch", db=db)
    open_branch.graph_version = GRAPH_VERSION - 1
    await open_branch.save(db=db)

    merged_branch = await create_branch(branch_name="merged-branch", db=db)
    merged_branch.graph_version = GRAPH_VERSION - 1
    merged_branch.status = BranchStatus.MERGED
    await merged_branch.save(db=db)

    deleting_branch = await create_branch(branch_name="deleting-branch", db=db)
    deleting_branch.graph_version = GRAPH_VERSION - 1
    deleting_branch.status = BranchStatus.DELETING
    await deleting_branch.save(db=db)

    flagged = await mark_branches_needing_rebase(db=db)

    flagged_names = {b.name for b in flagged}
    assert "open-branch" in flagged_names
    assert "merged-branch" not in flagged_names
    assert "deleting-branch" not in flagged_names

    refreshed_merged = await Branch.get_by_name(name="merged-branch", db=db)
    refreshed_deleting = await Branch.get_by_name(name="deleting-branch", db=db, ignore_deleting=False)
    assert refreshed_merged.status == BranchStatus.MERGED
    assert refreshed_deleting.status == BranchStatus.DELETING
