from abc import ABC, abstractmethod

from fast_depends import inject, Depends


class BranchMergeMutationChecker(ABC):
    @abstractmethod
    async def verify_branch_merge_mutation_allowed(
        self,
    ) -> None:
        raise NotImplementedError()


class BranchMergeMutationCheckerCommunity(BranchMergeMutationChecker):
    async def verify_branch_merge_mutation_allowed(
        self,
    ) -> None:
        pass


def get_branch_merge_mutation_checker() -> BranchMergeMutationChecker:
    return BranchMergeMutationCheckerCommunity()


@inject
async def verify_branch_merge_mutation_allowed(
    branch_merge_mutation_checker: BranchMergeMutationChecker = Depends(get_branch_merge_mutation_checker),  # noqa: B008
) -> None:
    await branch_merge_mutation_checker.verify_branch_merge_mutation_allowed()
