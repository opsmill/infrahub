from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.needs_rebase_status import raise_needs_rebase_error

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]


def raise_on_mutation_on_branch_needing_rebase(next, root, info, **kwargs):  # type: ignore  # noqa
    if info.context.branch.status == BranchStatus.NEED_REBASE and info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            raise_needs_rebase_error(branch_name=info.context.branch.name)

    return next(root, info, **kwargs)
