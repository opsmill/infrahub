import inspect

from infrahub.branch.status_checker import BranchStatusChecker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


async def raise_on_mutation_for_branch_status(next, root, info, **kwargs):  # type: ignore  # noqa
    # Only run the branch-status gate once per mutation, at the top-level mutation field.
    # The middleware fires for every resolved field; nested fields skip the DB checks.
    if info.operation.operation.value == "mutation" and info.path.prev is None:
        mutation_name = info.operation.selection_set.selections[0].name.value
        check_needs_rebase = mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH
        check_merge = mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH
        if check_needs_rebase or check_merge:
            await BranchStatusChecker(db=info.context.db).check(
                branch=info.context.branch,
                check_merge=check_merge,
                check_needs_rebase=check_needs_rebase,
            )

    result = next(root, info, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result
