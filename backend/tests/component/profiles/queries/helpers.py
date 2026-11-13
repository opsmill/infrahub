from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.profiles.queries.get_profile_data import RelationshipFilter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SITE = NodeSchema(name="Site", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
RACK = NodeSchema(name="Rack", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
LABEL = NodeSchema(name="Label", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
DEVICE = NodeSchema(
    name="Device",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="status", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="site",
            peer="TestSite",
            identifier="device__site",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
        RelationshipSchema(
            name="rack",
            peer="TestRack",
            identifier="device__rack",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
            optional=True,
        ),
        RelationshipSchema(
            name="labels",
            peer="TestLabel",
            identifier="device__label",
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
            optional=True,
        ),
    ],
)

SITE_FILTER = RelationshipFilter(relationship_identifier="profile_device__site", direction=RelationshipDirection.BIDIR)
RACK_FILTER = RelationshipFilter(
    relationship_identifier="profile_device__rack", direction=RelationshipDirection.OUTBOUND
)
LABELS_FILTER = RelationshipFilter(
    relationship_identifier="profile_device__label", direction=RelationshipDirection.INBOUND
)
ALL_FILTERS = [SITE_FILTER, RACK_FILTER, LABELS_FILTER]


@dataclass(frozen=True)
class Peers:
    sites: list[Node]
    racks: list[Node]
    labels: list[Node]


async def create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node
