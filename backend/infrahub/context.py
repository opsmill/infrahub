from pydantic import BaseModel, Field
from typing_extensions import Self

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch


class EventContext(BaseModel):
    name: str


class BranchContext(BaseModel):
    name: str
    id: str | None = None


class InfrahubContext(BaseModel):
    branch: BranchContext
    account: AccountSession
    events: list[EventContext] = Field(default_factory=list)

    @classmethod
    def init(cls, branch: Branch, account: AccountSession) -> Self:
        return cls(branch=BranchContext(name=branch.name, id=str(branch.uuid)), account=account)
