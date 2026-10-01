from dataclasses import dataclass

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, build_profile_schema


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


def _load_processed_branch(schema_root: SchemaRoot) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=SchemaRoot(**internal_schema))
    branch.load_schema(schema=SchemaRoot(**core_models))
    branch.load_schema(schema=schema_root)
    branch.process()
    return branch


class TestDiffIdenticalBranches:
    """A merge candidate built from two identical processed branches must produce an empty diff.

    This mirrors how a proposed change without schema modifications assembles its candidate
    schema; any reported diff there triggers pointless constraint validation across the branch.
    """

    def test_identical_branches_diff_empty(self, car_person_schema_root: SchemaRoot) -> None:
        dest_schema = _load_processed_branch(schema_root=car_person_schema_root)
        source_schema = dest_schema.duplicate()

        candidate_schema = dest_schema.duplicate()
        candidate_schema.update(schema=source_schema)

        assert dest_schema.diff(other=candidate_schema).all == []

    def test_identical_hierarchical_branches_diff_empty(self) -> None:
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
        dest_schema = _load_processed_branch(schema_root=schema_root)
        source_schema = dest_schema.duplicate()

        candidate_schema = dest_schema.duplicate()
        candidate_schema.update(schema=source_schema)

        assert dest_schema.diff(other=candidate_schema).all == []


class TestDeleteRemovesGeneratedKinds:
    """The profile and template generated from a kind must not outlive it in the schema maps.

    Between the delete and the next process() any reader would otherwise see a generated kind
    whose backing schema is gone, and reprocessing has to land on the schema that never held it.
    """

    @staticmethod
    def _gadget_and_widget_schema(with_gadget: bool) -> SchemaRoot:
        nodes = [
            NodeSchema(
                name="Widget",
                namespace="Testing",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
        ]
        if with_gadget:
            nodes.append(
                NodeSchema(
                    name="Gadget",
                    namespace="Testing",
                    generate_template=True,
                    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                )
            )
        return SchemaRoot(nodes=nodes)

    def test_reprocessing_after_delete_matches_schema_without_the_node(self) -> None:
        baseline = _load_processed_branch(schema_root=self._gadget_and_widget_schema(with_gadget=False))
        branch = _load_processed_branch(schema_root=self._gadget_and_widget_schema(with_gadget=True))

        branch.delete(name="TestingGadget")
        branch.process()

        assert branch.get_hash() == baseline.get_hash()
        assert sorted(branch.node_names) == sorted(baseline.node_names)
        assert sorted(branch.generic_names) == sorted(baseline.generic_names)
        assert sorted(branch.profile_names) == sorted(baseline.profile_names)
        assert sorted(branch.template_names) == sorted(baseline.template_names)

        hash_after_removal = branch.get_hash()
        branch.process()

        assert branch.get_hash() == hash_after_removal

    def test_delete_node_removes_its_template_and_profile(self) -> None:
        branch = _load_processed_branch(schema_root=self._gadget_and_widget_schema(with_gadget=True))
        assert "TemplateTestingGadget" in branch.template_names
        assert "ProfileTestingGadget" in branch.profile_names

        branch.delete(name="TestingGadget")

        assert "TemplateTestingGadget" not in branch.template_names
        assert "ProfileTestingGadget" not in branch.profile_names

    def test_delete_generic_removes_its_template(self) -> None:
        schema_root = SchemaRoot(
            generics=[
                GenericSchema(
                    name="Part",
                    namespace="Testing",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                ),
            ],
            nodes=[
                NodeSchema(
                    name="Gadget",
                    namespace="Testing",
                    generate_template=True,
                    inherit_from=["TestingPart"],
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                    ],
                ),
            ],
        )
        branch = _load_processed_branch(schema_root=schema_root)
        assert "TemplateTestingPart" in branch.generic_names

        branch.delete(name="TestingPart")

        assert "TemplateTestingPart" not in branch.generic_names


class TestProcessWithOrphanedTemplate:
    """A schema holding a generated template whose backing node is gone must reprocess cleanly.

    A registry can hold such an orphan when the node was removed without cleaning up the
    kinds generated from it; reprocessing must drop the orphan instead of failing.
    """

    def test_process_removes_orphaned_template_and_profile(self) -> None:
        schema_root = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Gadget",
                    namespace="Testing",
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                    ],
                ),
            ],
        )
        branch = _load_processed_branch(schema_root=schema_root)
        assert "TemplateTestingGadget" in branch.template_names
        assert "ProfileTestingGadget" in branch.profile_names

        # Drop the node from the map directly, bypassing the delete() cascade, to mirror
        # a registry that already holds an orphaned template
        del branch.nodes["TestingGadget"]

        branch.process()

        assert "TemplateTestingGadget" not in branch.template_names
        assert "ProfileTestingGadget" not in branch.profile_names


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


def _processed_profile_schema_branch(cross_relationship_hfid: bool) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=build_profile_schema(cross_relationship_hfid=cross_relationship_hfid))
    schema_branch.process()
    return schema_branch


def test_object_kinds_different_from_another_schema_branch() -> None:
    reference = _processed_profile_schema_branch(cross_relationship_hfid=False)
    changed = _processed_profile_schema_branch(cross_relationship_hfid=True)

    assert changed.get_object_kinds_different_from(reference) == [f"Profile{PROFILE_NODE_KIND}", PROFILE_NODE_KIND]
    assert (
        reference.get_object_kinds_different_from(_processed_profile_schema_branch(cross_relationship_hfid=False)) == []
    )


@dataclass(frozen=True, kw_only=True)
class HfidConstraintOrderCase:
    """Processed uniqueness constraints and human-friendly ID for one schema."""

    name: str
    kind: str
    schema_root: SchemaRoot
    expected_uniqueness_constraints: list[list[str]]
    expected_human_friendly_id: list[str]


def _device_interface_schema(
    *,
    human_friendly_id: list[str],
    uniqueness_constraints: list[list[str]] | None,
    extra_attribute_names: tuple[str, ...] = (),
) -> SchemaRoot:
    interface_attributes = [AttributeSchema(name="name", kind="Text")]
    interface_attributes.extend(
        AttributeSchema(name=attribute_name, kind="Text") for attribute_name in extra_attribute_names
    )
    copied_constraints = (
        [list(constraint) for constraint in uniqueness_constraints] if uniqueness_constraints is not None else None
    )
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Device",
                namespace="Testing",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Interface",
                namespace="Testing",
                human_friendly_id=list(human_friendly_id),
                uniqueness_constraints=copied_constraints,
                attributes=interface_attributes,
                relationships=[
                    RelationshipSchema(
                        name="device",
                        peer="TestingDevice",
                        optional=False,
                        kind=RelationshipKind.PARENT,
                        cardinality=RelationshipCardinality.ONE,
                        direction=RelationshipDirection.OUTBOUND,
                    )
                ],
            ),
        ]
    )


_INTERFACE_HFID = ["device__name__value", "name__value"]
_INTERFACE_HFID_CONSTRAINT = ["device", "name__value"]

HFID_CONSTRAINT_ORDER_CASES = [
    HfidConstraintOrderCase(
        name="reversed_relationship_fields",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[["name__value", "device"]],
        ),
        expected_uniqueness_constraints=[["name__value", "device"]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="same_order_relationship_fields",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[[*_INTERFACE_HFID_CONSTRAINT]],
        ),
        expected_uniqueness_constraints=[[*_INTERFACE_HFID_CONSTRAINT]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="no_constraint",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=None,
        ),
        expected_uniqueness_constraints=[[*_INTERFACE_HFID_CONSTRAINT]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="empty_constraint_list",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[],
        ),
        expected_uniqueness_constraints=[[*_INTERFACE_HFID_CONSTRAINT]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="unrelated_constraint",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[["status__value"]],
            extra_attribute_names=("status",),
        ),
        expected_uniqueness_constraints=[["status__value"], [*_INTERFACE_HFID_CONSTRAINT]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="subset_constraint",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[["name__value"]],
        ),
        expected_uniqueness_constraints=[["name__value"], [*_INTERFACE_HFID_CONSTRAINT]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="superset_constraint",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[["name__value", "device", "status__value"]],
            extra_attribute_names=("status",),
        ),
        expected_uniqueness_constraints=[
            ["name__value", "device", "status__value"],
            [*_INTERFACE_HFID_CONSTRAINT],
        ],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="equivalent_constraint_after_unrelated",
        kind="TestingInterface",
        schema_root=_device_interface_schema(
            human_friendly_id=_INTERFACE_HFID,
            uniqueness_constraints=[["status__value"], ["name__value", "device"]],
            extra_attribute_names=("status",),
        ),
        expected_uniqueness_constraints=[["status__value"], ["name__value", "device"]],
        expected_human_friendly_id=list(_INTERFACE_HFID),
    ),
    HfidConstraintOrderCase(
        name="reordered_attribute_fields",
        kind="TestingAsset",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Asset",
                    namespace="Testing",
                    human_friendly_id=["name__value", "serial__value"],
                    uniqueness_constraints=[["serial__value", "name__value"]],
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                        AttributeSchema(name="serial", kind="Text"),
                    ],
                )
            ]
        ),
        expected_uniqueness_constraints=[["serial__value", "name__value"]],
        expected_human_friendly_id=["name__value", "serial__value"],
    ),
]


@pytest.mark.parametrize(
    "case",
    [pytest.param(case, id=case.name) for case in HFID_CONSTRAINT_ORDER_CASES],
)
def test_processed_schema_keeps_one_hfid_constraint_per_field_set(case: HfidConstraintOrderCase) -> None:
    """Processing keeps one uniqueness constraint per HFID field set and preserves each list's order.

    A constraint listing the same fields in another order is the HFID constraint. A subset, superset,
    or unrelated constraint stays, and the HFID-derived constraint is appended in HFID order when absent.
    A second process leaves the constraints and the human-friendly ID unchanged.
    """
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=case.schema_root)

    for _ in range(2):
        branch.process()
        schema = branch.get(name=case.kind, duplicate=False)
        assert schema.uniqueness_constraints == case.expected_uniqueness_constraints
        assert schema.human_friendly_id == case.expected_human_friendly_id
