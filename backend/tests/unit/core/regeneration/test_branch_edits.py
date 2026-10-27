from __future__ import annotations

from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.regeneration.branch_edits import BranchEdit, edits_seen_since, edits_to_diff_summary
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, NodeSchema, RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp

BRANCH = "test/edits"
EDITED_AT = Timestamp("2026-10-01T12:00:00Z")

PERSON = NodeSchema(
    name="Person",
    namespace="Test",
    attributes=[AttributeSchema(name="name", kind="Text")],
    relationships=[
        RelationshipSchema(
            name="cars",
            peer="TestCar",
            kind=RelationshipKind.GENERIC,
            identifier="person__car",
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
        ),
    ],
)
CAR = NodeSchema(
    name="Car",
    namespace="Test",
    attributes=[AttributeSchema(name="color", kind="Text")],
    relationships=[
        RelationshipSchema(
            name="owner",
            peer="TestPerson",
            kind=RelationshipKind.ATTRIBUTE,
            identifier="person__car",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
    ],
)


def _schema_branch() -> SchemaBranch:
    schemas: dict[str, MainSchemaTypes] = {"TestPerson": PERSON, "TestCar": CAR}
    branch = SchemaBranch(cache={}, name="test")
    for kind, schema in schemas.items():
        branch.set(name=kind, schema=schema)
    return branch


def _element(name: str, element_type: str) -> NodeDiffElement:
    return NodeDiffElement(
        name=name, element_type=element_type, action="UPDATED", summary=NodeDiffSummary(added=0, updated=1, removed=0)
    )


def _edit(node_id: str, kind: str, field_name: str, is_relationship: bool) -> BranchEdit:
    return BranchEdit(
        node_id=node_id, kind=kind, field_name=field_name, is_relationship=is_relationship, edited_at=EDITED_AT
    )


def test_edits_become_updated_diff_entries_per_node() -> None:
    """Each edited node becomes one updated entry listing its edited attributes and relationships by name."""
    edits = [
        _edit("car-1", "TestCar", "color", is_relationship=False),
        _edit("car-1", "TestCar", "person__car", is_relationship=True),
        _edit("person-1", "TestPerson", "person__car", is_relationship=True),
        _edit("person-1", "TestPerson", "name", is_relationship=False),
    ]

    summary = edits_to_diff_summary(edits=edits, branch_name=BRANCH, schema_branch=_schema_branch())

    assert summary == [
        NodeDiff(
            branch=BRANCH,
            kind="TestCar",
            id="car-1",
            action="UPDATED",
            display_label="",
            elements=[_element("color", "ATTRIBUTE"), _element("owner", "RELATIONSHIP_ONE")],
        ),
        NodeDiff(
            branch=BRANCH,
            kind="TestPerson",
            id="person-1",
            action="UPDATED",
            display_label="",
            elements=[_element("cars", "RELATIONSHIP_MANY"), _element("name", "ATTRIBUTE")],
        ),
    ]


def test_edits_on_unknown_kinds_or_relationships_are_left_out() -> None:
    """An edit on a kind missing from the schema, or on a relationship the kind does not carry, adds nothing."""
    edits = [
        _edit("ghost-1", "TestGhost", "name", is_relationship=False),
        _edit("car-1", "TestCar", "car__unknown", is_relationship=True),
    ]

    assert edits_to_diff_summary(edits=edits, branch_name=BRANCH, schema_branch=_schema_branch()) == []


def test_edits_seen_since_leaves_out_nodes_created_after_the_check_and_already_removed() -> None:
    """Only edits after the time count, and a node created after the latest check and removed since is left out."""
    latest_check = Timestamp("2026-10-01T12:00:00Z")
    since = Timestamp("2026-10-01T11:00:00Z")
    early = BranchEdit(
        node_id="car-early",
        kind="TestCar",
        field_name="color",
        is_relationship=False,
        edited_at=Timestamp("2026-10-01T10:00:00Z"),
    )
    kept = BranchEdit(
        node_id="car-kept", kind="TestCar", field_name="color", is_relationship=False, edited_at=EDITED_AT
    )
    seen_then_removed = BranchEdit(
        node_id="car-seen",
        kind="TestCar",
        field_name="color",
        is_relationship=False,
        edited_at=Timestamp("2026-10-01T13:00:00Z"),
        node_created_at=Timestamp("2026-10-01T11:30:00Z"),
        node_removed_at=Timestamp("2026-10-01T13:00:00Z"),
    )
    never_seen = BranchEdit(
        node_id="car-unseen",
        kind="TestCar",
        field_name="color",
        is_relationship=False,
        edited_at=Timestamp("2026-10-01T13:00:00Z"),
        node_created_at=Timestamp("2026-10-01T12:30:00Z"),
        node_removed_at=Timestamp("2026-10-01T13:00:00Z"),
    )
    created_and_kept = BranchEdit(
        node_id="car-new",
        kind="TestCar",
        field_name="color",
        is_relationship=False,
        edited_at=Timestamp("2026-10-01T13:00:00Z"),
        node_created_at=Timestamp("2026-10-01T12:30:00Z"),
    )

    result = edits_seen_since(
        edits=[early, kept, seen_then_removed, never_seen, created_and_kept], since=since, latest_check=latest_check
    )

    assert result == [kept, seen_then_removed, created_and_kept]
