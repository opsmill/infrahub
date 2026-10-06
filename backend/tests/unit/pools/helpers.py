from __future__ import annotations

from infrahub.core.attribute import String
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp

TICKET_KIND = "TestingTicket"


class InMemoryNumberPool(CoreNumberPool):
    """A number pool held in memory, carrying only the attributes that decide who may draw from it."""

    def __init__(self, id: str, name: str, node: str = TICKET_KIND, node_attribute: str = "ticket_id") -> None:
        self.id = id
        branch = Branch(name="main")
        at = Timestamp()
        attribute_schemas = [
            AttributeSchema(name=attr_name, kind="Text") for attr_name in ("name", "node", "node_attribute")
        ]
        owner = Node(
            schema=NodeSchema(name="NumberPool", namespace="Core", attributes=attribute_schemas), branch=branch, at=at
        )
        owner.id = id
        name_schema, node_schema, node_attribute_schema = attribute_schemas
        self.name = String(name="name", schema=name_schema, branch=branch, at=at, node=owner, data=name)
        self.node = String(name="node", schema=node_schema, branch=branch, at=at, node=owner, data=node)
        self.node_attribute = String(
            name="node_attribute", schema=node_attribute_schema, branch=branch, at=at, node=owner, data=node_attribute
        )

    def get_id(self) -> str:
        return self.id
