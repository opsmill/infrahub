from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


class ProposedChangeChecker(ABC):
    # We can't use CoreProposedChange type instead of Node as fast_depends enforces pydantic runtime type checks.
    @abstractmethod
    async def can_merge_proposed_change(self, proposed_change: Node, db: InfrahubDatabase) -> str | None:
        """
        Returns None if proposed change can be merged, otherwise returns the error message.
        """

        raise NotImplementedError()


class ProposedChangeCheckerCommunity(ProposedChangeChecker):
    async def can_merge_proposed_change(self, proposed_change: Node, db: InfrahubDatabase) -> str | None:  # noqa: ARG002
        return None


def get_proposed_change_checker() -> ProposedChangeChecker:
    return ProposedChangeCheckerCommunity()


# We can't use CoreProposedChange type instead of Node as fast_depends enforces pydantic runtime type checks.
@inject
async def can_merge_proposed_change(
    proposed_change: Node,
    db: InfrahubDatabase,
    pc_checker: ProposedChangeChecker = Depends(get_proposed_change_checker),  # noqa: B008
) -> str | None:
    # type ignore due to fast-depends enforcing pydantic checks
    return await pc_checker.can_merge_proposed_change(proposed_change=proposed_change, db=db)  # type: ignore
