from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


@runtime_checkable
class Brancher(Protocol):
    @classmethod
    async def get_by_name(cls, name: str, session: AsyncSession) -> Branch:
        raise NotImplementedError()

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)
