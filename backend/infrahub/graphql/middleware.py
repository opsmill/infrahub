from inspect import isawaitable

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.merge.write_blocker import MergeWriteBlocker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


async def raise_on_mutation_for_branch_status(next, root, info, **kwargs):  # type: ignore  # noqa
    # Only gate at the top-level mutation field so the merge-protection cache key is read once per
    # mutation rather than once per resolved field.
    if info.operation.operation.value == "mutation" and info.path.prev is None:
        mutation_name = info.operation.selection_set.selections[0].name.value
        merge_write_blocker = MergeWriteBlocker(cache=info.context.active_service.cache)
        branch_status_checker = BranchStatusChecker(db=info.context.db, merge_write_blocker=merge_write_blocker)
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            branch_status_checker.check_needs_rebase_status(branch=info.context.branch)
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            branch_status_checker.check_merge_status(branch=info.context.branch)
        await branch_status_checker.check_merging_status(branch=info.context.branch)

    result = next(root, info, **kwargs)
    if isawaitable(result):
        return await result
    return result
