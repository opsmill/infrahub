import pytest

from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


class TestDeriveHumanFriendlyIdWithRelationshipOnlyConstraint:
    """A single-element relationship-only uniqueness_constraint must not crash HFID derivation."""

    @pytest.fixture
    def processed_branch(self) -> SchemaBranch:
        schema_root = SchemaRoot(
            generics=[
                GenericSchema(
                    name="Location",
                    namespace="Testing",
                    hierarchical=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
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
                    uniqueness_constraints=[["parent"]],
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

    def test_process_human_friendly_id_does_not_raise(self, processed_branch: SchemaBranch) -> None:
        """The HFID derivation must resolve a parent-only constraint without crashing."""
        processed_branch.process_human_friendly_id(raise_parsing_errors=True)

        site = processed_branch.get(name="TestingSite", duplicate=False)
        assert site.human_friendly_id is None


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
