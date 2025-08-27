from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.auth import AccountSession
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


class ProposedChangeChecker(ABC):
    # We can't use CoreProposedChange type instead of Node as fast_depends enforces pydantic runtime type checks.
    @abstractmethod
    async def verify_proposed_change_is_mergeable(
        self, proposed_change: Node, db: InfrahubDatabase, account_session: AccountSession
    ) -> None:
        """
        Raise an error if proposed change cannot be merged.
        """

        raise NotImplementedError()


class ProposedChangeCheckerCommunity(ProposedChangeChecker):
    async def verify_proposed_change_is_mergeable(
        self, proposed_change: Node, db: InfrahubDatabase, account_session: AccountSession
    ) -> None:
        pass


def get_proposed_change_checker() -> ProposedChangeChecker:
    return ProposedChangeCheckerCommunity()


# We can't use CoreProposedChange type instead of Node as fast_depends enforces pydantic runtime type checks.
@inject
async def verify_proposed_change_is_mergeable(
    proposed_change: Node,
    db: InfrahubDatabase,
    account_session: AccountSession,
    pc_checker: ProposedChangeChecker = Depends(get_proposed_change_checker),  # noqa: B008
) -> None:
    # type ignore due to fast-depends enforcing pydantic checks
    await pc_checker.verify_proposed_change_is_mergeable(
        proposed_change=proposed_change, db=db, account_session=account_session
    )
