from infrahub.core.branch.merged_status import check_merged_status
from infrahub.core.branch.needs_rebase_status import check_need_rebase_status

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


def raise_on_mutation_for_branch_status(next, root, info, **kwargs):  # type: ignore  # noqa
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            check_need_rebase_status(branch=info.context.branch)
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            check_merged_status(branch=info.context.branch)

    return next(root, info, **kwargs)
