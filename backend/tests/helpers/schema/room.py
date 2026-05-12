"""Schema builder for relationships whose declared peer is a generic.

A ``TestRoom`` generic exposes two concrete subtypes:

- ``TestSingleRoom`` — always cardinality=one (a single room holds one occupant).
- ``TestDorm`` — always cardinality=many; an optional ``max_count`` / ``min_count``
  can be set to bound the number of occupants.

``TestPerson`` declares a ``rooms`` relationship whose peer is the generic
``TestRoom``. Builder parameters control whether the cardinality constraints
sit on the generic or only on the concrete subtypes, and the relationship
directions.
"""

from typing import Any

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)


def _occupant_rel(
    *,
    cardinality: RelationshipCardinality,
    direction: RelationshipDirection,
    max_count: int | None = None,
    min_count: int | None = None,
) -> RelationshipSchema:
    kwargs: dict[str, Any] = {
        "name": "occupant",
        "peer": "TestPerson",
        "identifier": "person__room",
        "cardinality": cardinality,
        "optional": True,
        "direction": direction,
    }
    if max_count is not None:
        kwargs["max_count"] = max_count
    if min_count is not None:
        kwargs["min_count"] = min_count
    return RelationshipSchema(**kwargs)


def build_room_schema(
    *,
    generic_has_rel: bool = False,
    include_dorm_subtype: bool = False,
    dorm_max_count: int | None = None,
    dorm_min_count: int | None = None,
    occupant_direction: str = "inbound",
    rooms_direction: str = "outbound",
) -> SchemaRoot:
    direction = RelationshipDirection(occupant_direction)
    single_occupant = _occupant_rel(cardinality=RelationshipCardinality.ONE, direction=direction)

    # The generic carries the ``cardinality=one`` declaration only when explicitly
    # asked (``generic_has_rel=True``); otherwise the rel lives solely on the subtypes.
    room = GenericSchema(
        name="Room",
        namespace="Test",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        relationships=[single_occupant] if generic_has_rel else [],
    )

    nodes: list[NodeSchema] = [
        NodeSchema(
            name="SingleRoom",
            namespace="Test",
            inherit_from=["TestRoom"],
            relationships=[] if generic_has_rel else [single_occupant],
        )
    ]

    if include_dorm_subtype:
        dorm_occupant = _occupant_rel(
            cardinality=RelationshipCardinality.MANY,
            direction=direction,
            max_count=dorm_max_count,
            min_count=dorm_min_count,
        )
        nodes.append(
            NodeSchema(
                name="Dorm",
                namespace="Test",
                inherit_from=["TestRoom"],
                relationships=[] if generic_has_rel else [dorm_occupant],
            )
        )

    nodes.append(
        NodeSchema(
            name="Person",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="rooms",
                    peer="TestRoom",
                    identifier="person__room",
                    cardinality=RelationshipCardinality.MANY,
                    optional=True,
                    direction=RelationshipDirection(rooms_direction),
                )
            ],
        )
    )

    return SchemaRoot(generics=[room], nodes=nodes)
