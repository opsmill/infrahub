from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch.branch import Branch
    from infrahub.database import InfrahubDatabase


@runtime_checkable
class Brancher(Protocol):
    @classmethod
    async def get_by_name(
        cls, name: str, session: Optional[AsyncSession] = None, db: Optional[InfrahubDatabase] = None
    ) -> Branch:
        raise NotImplementedError()

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)
