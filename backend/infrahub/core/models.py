from infrahub.core.node import Node

# pylint: disable=no-member


class NodeSchema(Node):
    pass


class RelationshipSchema(Node):
    pass
    # async def process_identifier(self, session: AsyncSession) -> None:
    #     if self.identifier.value:
    #         return None

    #     if hasattr(self, "node") and getattr(self, "node"):
    #         node = await self.node.get_peer(session=session)
    #         if node.kind.value and self.peer.value:
    #             identifier = "__".join(sorted([node.kind.value, self.peer.value]))
    #             self.identifier.value = identifier.lower()
