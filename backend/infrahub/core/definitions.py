from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

from infrahub.core.node import Node

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.attribute import HashedPassword, String, StringMandatory
    from infrahub.core.branch import Branch
    from infrahub.core.relationship import RelationshipManager
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


# implemented using standard inheritance
class CoreAccountNode(Node):
    name: String
    password: HashedPassword
    label: String
    description: String
    type: String
    role: StringMandatory
    tokens: RelationshipManager


# implemented using Protocol
class CoreNode(Protocol):
    id: str

    async def save(self):
        ...


class CoreAccountProtocol(CoreNode):
    name: String
    password: HashedPassword
    label: String
    description: String
    type: String
    role: StringMandatory
    tokens: RelationshipManager
