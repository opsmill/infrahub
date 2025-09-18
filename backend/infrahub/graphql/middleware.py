from infrahub.core.branch.needs_rebase_status import check_need_rebase_status

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]


def raise_on_mutation_on_branch_needing_rebase(next, root, info, **kwargs):  # type: ignore  # noqa
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            check_need_rebase_status(branch=info.context.branch)

    return next(root, info, **kwargs)
