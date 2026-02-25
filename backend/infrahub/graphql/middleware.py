from infrahub.branch.status_checker import BranchStatusChecker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


def raise_on_mutation_for_branch_status(next, root, info, **kwargs):  # type: ignore  # noqa
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        brach_status_checker = BranchStatusChecker()
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            brach_status_checker.check_needs_rebase_status(branch=info.context.branch)
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            brach_status_checker.check_merge_status(branch=info.context.branch)

    return next(root, info, **kwargs)
