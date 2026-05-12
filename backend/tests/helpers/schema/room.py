"""Schema builder for relationships whose declared peer is a generic.

A ``TestRoom`` generic exposes two concrete subtypes:

- ``TestSingleRoom`` — each room holds at most one occupant (cardinality=one).
- ``TestDorm`` — a dorm may hold many occupants (cardinality=many).

``TestPerson`` declares a ``rooms`` relationship whose peer is the generic
``TestRoom``. Builder parameters control whether the cardinality constraint
sits on the generic or only on the concrete subtype, the constraint type
(cardinality, max_count, min_count), and the relationship directions.
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
    single_room_cardinality: str = "one",
    single_room_max_count: int | None = None,
    single_room_min_count: int | None = None,
    include_dorm_subtype: bool = False,
    single_room_direction: str = "inbound",
    person_direction: str = "outbound",
) -> SchemaRoot:
    direction = RelationshipDirection(single_room_direction)
    single_occupant = _occupant_rel(
        cardinality=RelationshipCardinality(single_room_cardinality),
        direction=direction,
        max_count=single_room_max_count,
        min_count=single_room_min_count,
    )

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
                    direction=RelationshipDirection(person_direction),
                )
            ],
        )
    )

    return SchemaRoot(generics=[room], nodes=nodes)
