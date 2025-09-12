from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.auth import AccountSession
from infrahub.database import InfrahubDatabase


class BranchMergeMutationChecker(ABC):
    @abstractmethod
    async def verify_branch_merge_mutation_allowed(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
    ) -> None:
        raise NotImplementedError()


class BranchMergeMutationCheckerCommunity(BranchMergeMutationChecker):
    async def verify_branch_merge_mutation_allowed(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
    ) -> None:
        pass


def get_branch_merge_mutation_checker() -> BranchMergeMutationChecker:
    return BranchMergeMutationCheckerCommunity()


@inject
async def verify_branch_merge_mutation_allowed(
    db: InfrahubDatabase,
    account_session: AccountSession,
    branch_merge_mutation_checker: BranchMergeMutationChecker = Depends(get_branch_merge_mutation_checker),  # noqa: B008
) -> None:
    await branch_merge_mutation_checker.verify_branch_merge_mutation_allowed(db=db, account_session=account_session)
