from neo4j import AsyncSession

from infrahub.core.node import Node


class NodeSchema(Node):
    pass


class RelationshipSchema(Node):
    async def process_identifier(self, session: AsyncSession) -> None:
        if self.identifier.value:
            return None

        if hasattr(self, "node") and getattr(self, "node"):
            node = await self.node.get_peer(session=session)
            identifier = "__".join(sorted([node.kind.value, self.peer.value]))
            self.identifier.value = identifier.lower()
