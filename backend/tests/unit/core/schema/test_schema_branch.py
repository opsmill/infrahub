from typing import Any

import pytest

from infrahub.core.constants import BranchSupportType, HashableModelState
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


def test_strip_removed_paths_drops_whole_multi_path_uniqueness_group() -> None:
    node = NodeSchema(name="Thing", namespace="Testing")
    node.uniqueness_constraints = [["name__value", "old_id__value"], ["name__value"]]

    SchemaBranch._strip_removed_paths_from_identity_fields(node=node, removed_names=["old_id"])

    assert node.uniqueness_constraints == [["name__value"]]


def test_strip_removed_paths_handles_relationship_name_prefixes() -> None:
    node = NodeSchema(name="Thing", namespace="Testing")
    node.uniqueness_constraints = [["tenant__name__value"]]
    node.human_friendly_id = ["tenant__name__value"]
    node.order_by = ["tenant__name__value"]
    node.display_labels = ["tenant__name__value"]

    SchemaBranch._strip_removed_paths_from_identity_fields(node=node, removed_names=["tenant"])

    assert node.uniqueness_constraints is None
    assert node.human_friendly_id is None
    assert node.order_by is None
    assert node.display_labels is None


def test_schema_branch_cleanup_inherited_elements_strips_stale_identity_paths() -> None:
    schema_dict: dict[str, Any] = {
        "generics": [
            {
                "name": "Parent",
                "namespace": "Testing",
                "branch": BranchSupportType.AGNOSTIC.value,
                "uniqueness_constraints": [["old_id__value"]],
                "human_friendly_id": ["old_id__value"],
                "order_by": ["old_id__value"],
                "display_labels": ["old_id__value"],
                "default_filter": "old_id__value",
                "attributes": [
                    {"name": "old_id", "kind": "Number", "optional": True},
                    {"name": "new_id", "kind": "Number", "optional": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Child",
                "namespace": "Testing",
                "branch": BranchSupportType.AGNOSTIC.value,
                "inherit_from": ["TestingParent"],
            },
        ],
    }
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_dict))
    schema.process()

    child = schema.get(name="TestingChild")
    assert child.uniqueness_constraints == [["old_id__value"]]
    assert child.human_friendly_id == ["old_id__value"]
    assert child.order_by == ["old_id__value"]
    assert child.display_labels == ["old_id__value"]
    assert child.default_filter == "old_id__value"

    generic = schema.get(name="TestingParent")
    generic.get_attribute(name="old_id").state = HashableModelState.ABSENT
    schema.set(name=generic.kind, schema=generic)

    schema.cleanup_inherited_elements()

    child = schema.get(name="TestingChild")
    assert child.get_attribute(name="old_id").state == HashableModelState.ABSENT
    assert not child.uniqueness_constraints
    assert not child.human_friendly_id
    assert not child.order_by
    assert not child.display_labels
    assert child.default_filter is None


def test_cleanup_inherited_elements_strips_locally_defined_identity_fields() -> None:
    schema_dict: dict[str, Any] = {
        "generics": [
            {
                "name": "Parent",
                "namespace": "Testing",
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "old_id", "kind": "Number", "optional": True},
                    {"name": "name", "kind": "Text", "optional": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Child",
                "namespace": "Testing",
                "branch": BranchSupportType.AGNOSTIC.value,
                "inherit_from": ["TestingParent"],
                "uniqueness_constraints": [["old_id__value"]],
                "human_friendly_id": ["old_id__value"],
            },
        ],
    }
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_dict))
    schema.process()

    child = schema.get(name="TestingChild")
    assert child.uniqueness_constraints == [["old_id__value"]]
    assert child.human_friendly_id == ["old_id__value"]

    generic = schema.get(name="TestingParent")
    generic.get_attribute(name="old_id").state = HashableModelState.ABSENT
    schema.set(name=generic.kind, schema=generic)

    schema.cleanup_inherited_elements()

    child = schema.get(name="TestingChild")
    assert not child.uniqueness_constraints
    assert not child.human_friendly_id


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
