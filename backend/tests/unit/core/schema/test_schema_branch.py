from dataclasses import dataclass

import pytest

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


@dataclass
class DoubleUnderscoreNameCase:
    name: str
    """Descriptive name for the test scenario."""

    schema_root: SchemaRoot
    """Schema whose validation must reject a name containing the schema-path separator."""

    offending_name: str
    """The attribute or relationship name that contains '__' and should be rejected."""


DOUBLE_UNDERSCORE_NAME_CASES: list[DoubleUnderscoreNameCase] = [
    DoubleUnderscoreNameCase(
        name="attribute_name_with_double_underscore_is_rejected",
        schema_root=SchemaRoot(
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
        offending_name="name__asc",
    ),
    DoubleUnderscoreNameCase(
        name="relationship_name_with_double_underscore_is_rejected",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Underscore",
                    namespace="Testing",
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                    ],
                    relationships=[
                        RelationshipSchema(name="peer__link", peer="TestingUnderscore", optional=True),
                    ],
                ),
            ],
        ),
        offending_name="peer__link",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in DOUBLE_UNDERSCORE_NAME_CASES],
)
def test_double_underscores_in_names_are_rejected(test_case: DoubleUnderscoreNameCase) -> None:
    """Schema validation must reject attribute/relationship names containing '__'.

    '__' is the schema path separator (e.g. ``name__value``), so any name that
    contains it collides with the path-splitting logic and cannot be referenced.
    """
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=test_case.schema_root)

    with pytest.raises(ValueError, match=test_case.offending_name):
        schema.process_validate()


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
