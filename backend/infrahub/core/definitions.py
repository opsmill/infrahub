from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@runtime_checkable
class Brancher(Protocol):
    @classmethod
    async def get_by_name(cls, name: str, db: InfrahubDatabase) -> Branch:
        raise NotImplementedError()

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)


@runtime_checkable
class NodeInfo(Protocol):
    def get_kind(self) -> str:
        raise NotImplementedError()

    def get_id(self) -> str:
        raise NotImplementedError()
