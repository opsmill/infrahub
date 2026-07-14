import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDeleteBehavior, RelationshipKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


def test_single_relationship_uniqueness_constraint(car_person_schema_root: SchemaRoot) -> None:
    """The HFID derivation must resolve a parent-only constraint without crashing."""
    car_schema = next(n for n in car_person_schema_root.nodes if n.name == "Car")
    car_schema.uniqueness_constraints = [["owner"]]
    for attribute_schema in car_schema.attributes:
        attribute_schema.unique = False

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=car_person_schema_root)
    schema_branch.process()

    processed_car_schema = schema_branch.get(name="TestCar", duplicate=False)
    assert processed_car_schema.uniqueness_constraints == [["owner"]]
    assert processed_car_schema.human_friendly_id is None


def test_validate_names_rejects_double_underscore_in_attribute_name() -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Underscore",
                    namespace="Testing",
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                        AttributeSchema(name="name__asc", kind="Text"),
                    ],
                ),
            ],
        ),
    )

    with pytest.raises(
        ValueError,
        match=r"TestingUnderscore: 'name__asc' cannot be used as an attribute name",
    ):
        schema.validate_names()


def test_validate_names_rejects_double_underscore_in_relationship_name() -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Underscore",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(name="peer__link", peer="TestingUnderscore", optional=True),
                    ],
                ),
            ],
        ),
    )

    with pytest.raises(
        ValueError,
        match=r"TestingUnderscore: 'peer__link' cannot be used as a relationship name",
    ):
        schema.validate_names()


def test_changing_relationship_kind_from_component_recomputes_on_delete() -> None:
    """Changing a relationship's kind away from Component must recompute on_delete to NO_ACTION."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Gadget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                ),
                NodeSchema(
                    name="Widget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="gadgets",
                            peer="TestingGadget",
                            kind=RelationshipKind.COMPONENT,
                            cardinality=RelationshipCardinality.MANY,
                            optional=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    schema.process()

    widget = schema.get(name="TestingWidget", duplicate=False)
    assert widget.get_relationship(name="gadgets").on_delete == RelationshipDeleteBehavior.CASCADE

    # Change the relationship kind from Component to Attribute, mirroring an in-place schema
    # update. on_delete is intentionally left unset — it is a derived field users do not set.
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="gadgets",
                            peer="TestingGadget",
                            kind=RelationshipKind.ATTRIBUTE,
                            cardinality=RelationshipCardinality.MANY,
                            optional=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    schema.process()

    widget = schema.get(name="TestingWidget", duplicate=False)
    updated_rel = widget.get_relationship(name="gadgets")
    assert updated_rel.kind == RelationshipKind.ATTRIBUTE
    assert updated_rel.on_delete == RelationshipDeleteBehavior.NO_ACTION


def test_changing_relationship_kind_preserves_explicit_on_delete_override() -> None:
    """An on_delete that diverges from the kind default is an explicit override and must survive a kind change."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Gadget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                ),
                NodeSchema(
                    name="Widget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="gadgets",
                            peer="TestingGadget",
                            kind=RelationshipKind.GENERIC,
                            cardinality=RelationshipCardinality.MANY,
                            optional=True,
                            on_delete=RelationshipDeleteBehavior.CASCADE,
                        ),
                    ],
                ),
            ],
        ),
    )
    schema.process()

    widget = schema.get(name="TestingWidget", duplicate=False)
    assert widget.get_relationship(name="gadgets").on_delete == RelationshipDeleteBehavior.CASCADE

    # Change the kind but do not restate on_delete. Because CASCADE diverges from the Generic
    # default (NO_ACTION), it is a deliberate override and must be kept.
    schema.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="gadgets",
                            peer="TestingGadget",
                            kind=RelationshipKind.ATTRIBUTE,
                            cardinality=RelationshipCardinality.MANY,
                            optional=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    schema.process()

    widget = schema.get(name="TestingWidget", duplicate=False)
    assert widget.get_relationship(name="gadgets").on_delete == RelationshipDeleteBehavior.CASCADE


class TestHierarchySchemaProcessingSetsCorrectPeerAndHierarchical:
    """Proves that schema processing produces the peer/hierarchical values in an expected manner."""

    @pytest.fixture(scope="class")
    def processed_schema(self) -> SchemaBranch:
        schema_root = SchemaRoot(
            generics=[
                GenericSchema(
                    name="Location",
                    namespace="Testing",
                    hierarchical=True,
                    default_filter="name__value",
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                    ],
                ),
            ],
            nodes=[
                NodeSchema(
                    name="Country",
                    namespace="Testing",
                    inherit_from=["TestingLocation"],
                    parent="",
                    children="TestingSite",
                ),
                NodeSchema(
                    name="Site",
                    namespace="Testing",
                    inherit_from=["TestingLocation"],
                    parent="TestingCountry",
                    children="",
                ),
            ],
        )
        branch = SchemaBranch(cache={}, name="test")
        branch.load_schema(schema=schema_root)
        branch.process_inheritance()
        branch.process_hierarchy()
        branch.add_hierarchy_generic()
        branch.add_hierarchy_node()
        return branch

    def test_concrete_node_parent_has_peer_different_from_hierarchical(self, processed_schema: SchemaBranch) -> None:
        """On a concrete node, parent.peer is the concrete parent kind while hierarchical is the generic."""
        site = processed_schema.get("TestingSite", duplicate=False)
        parent_rel = site.get_relationship(name="parent")

        assert parent_rel.peer == "TestingCountry"
        assert parent_rel.hierarchical == "TestingLocation"
        assert parent_rel.peer != parent_rel.hierarchical

    def test_generic_parent_has_peer_equal_to_hierarchical(self, processed_schema: SchemaBranch) -> None:
        """On the generic itself, parent.peer and hierarchical are both the generic kind."""
        generic = processed_schema.get("TestingLocation", duplicate=False)
        parent_rel = generic.get_relationship(name="parent")

        assert parent_rel.peer == "TestingLocation"
        assert parent_rel.hierarchical == "TestingLocation"
        assert parent_rel.peer == parent_rel.hierarchical
