import pytest

from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.attribute_schema import TextAttributeSchema
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


def test_local_attribute_keeps_its_branch_support_over_the_generic() -> None:
    """An attribute redefined on a node must not pick up the branch support of the generic's own copy.

    Generics may declare an attribute that every implementer carries while the implementers scope it
    differently, so the local definition has to win outright.
    """
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(
        schema=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Item",
                    namespace="Testing",
                    branch=BranchSupportType.AGNOSTIC,
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                        AttributeSchema(name="revision", kind="Text", branch=BranchSupportType.LOCAL),
                    ],
                )
            ],
            nodes=[
                NodeSchema(
                    name="Note",
                    namespace="Testing",
                    branch=BranchSupportType.AGNOSTIC,
                    inherit_from=["TestingItem"],
                    attributes=[AttributeSchema(name="revision", kind="Text", branch=BranchSupportType.AWARE)],
                )
            ],
        )
    )
    schema_branch.process()

    generic_revision = schema_branch.get_generic(name="TestingItem", duplicate=False).get_attribute(name="revision")
    assert generic_revision.branch == BranchSupportType.LOCAL

    node_revision = schema_branch.get_node(name="TestingNote", duplicate=False).get_attribute(name="revision")
    assert node_revision.branch == BranchSupportType.AWARE
    assert node_revision.inherited is False


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


@pytest.mark.parametrize(
    ("uniqueness_constraints", "expected"),
    [
        pytest.param([["name__value", "owner"]], [["name__value", "owner"]], id="same_fields_reordered"),
        pytest.param([["name__value"]], [["name__value"], ["owner", "name__value"]], id="subset"),
        pytest.param(
            [["name__value", "owner", "color__value"]],
            [["name__value", "owner", "color__value"], ["owner", "name__value"]],
            id="superset",
        ),
    ],
)
def test_hfid_constraint_matches_existing_constraint_by_field_set(
    car_person_schema_root: SchemaRoot, uniqueness_constraints: list[list[str]], expected: list[list[str]]
) -> None:
    """A constraint with the HFID's fields in another order counts as the HFID constraint."""
    car_schema = next(n for n in car_person_schema_root.nodes if n.name == "Car")
    car_schema.human_friendly_id = ["owner__name__value", "name__value"]
    car_schema.uniqueness_constraints = uniqueness_constraints
    for attribute_schema in car_schema.attributes:
        attribute_schema.unique = False

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=car_person_schema_root)
    schema_branch.process()

    assert schema_branch.get(name="TestCar", duplicate=False).uniqueness_constraints == expected


def test_rejects_malformed_existing_constraint_with_corrected_hfid(car_person_schema_root: SchemaRoot) -> None:
    schema_branch = _load_processed_branch(schema_root=car_person_schema_root)
    node = schema_branch.get(name="TestCar", duplicate=False)
    node.human_friendly_id = ["name__value", "color__value"]
    node.uniqueness_constraints = [["name__value__color__value"]]

    with pytest.raises(
        ValueError,
        match=r"^TestCar: Requested unique constraint not found within node\. \(`name__value__color__value`\)$",
    ):
        schema_branch.process()


def test_malformed_hfid_is_not_propagated_to_constraints(car_person_schema_root: SchemaRoot) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=car_person_schema_root)
    node = schema_branch.get(name="TestCar", duplicate=False)
    node.human_friendly_id = ["name__value__color__value"]
    node.uniqueness_constraints = []

    schema_branch.process_human_friendly_id(raise_parsing_errors=False)

    assert schema_branch.get(name="TestCar").uniqueness_constraints == []
    with pytest.raises(
        ValueError,
        match=r"^TestCar\.human_friendly_id: name__value__color__value has too many segments on schema TestCar$",
    ):
        schema_branch.validate_human_friendly_id()


def _set_attribute(branch: SchemaBranch, node_kind: str, attribute: str, **values: object) -> None:
    node = branch.get(name=node_kind)
    attribute_schema = node.get_attribute(name=attribute)
    for name, value in values.items():
        setattr(attribute_schema, name, value)
    branch.set(name=node_kind, schema=node)


def _candidate(base: SchemaBranch, destination: SchemaBranch, source: SchemaBranch) -> SchemaBranch:
    candidate = destination.duplicate()
    candidate.apply_changes_since(base=base, schema=source)
    return candidate


def _with_vehicle_nodes(schema_root: SchemaRoot, names: list[str]) -> SchemaRoot:
    schema_root = schema_root.model_copy(deep=True)
    schema_root.nodes.extend(
        NodeSchema(
            name=name,
            namespace="Test",
            inherit_from=["TestVehicle"],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
        for name in names
    )
    return schema_root


def _with_vehicle_generic(schema_root: SchemaRoot, wheels_description: str) -> SchemaRoot:
    schema_root = schema_root.model_copy(deep=True)
    schema_root.generics = [
        GenericSchema(
            name="Vehicle",
            namespace="Test",
            attributes=[AttributeSchema(name="wheels", kind="Number", optional=True, description=wheels_description)],
        )
    ]
    car = next(node for node in schema_root.nodes if node.name == "Car")
    car.inherit_from = ["TestVehicle"]
    return schema_root


class TestApplyChangesSince:
    """The candidate of a merge holds the destination's schema plus the changes the source made since the base."""

    @pytest.fixture
    def base(self, car_person_schema_root: SchemaRoot) -> SchemaBranch:
        return _load_processed_branch(schema_root=car_person_schema_root)

    def test_keeps_a_property_changed_on_the_destination_only(self, base: SchemaBranch) -> None:
        destination = base.duplicate()
        _set_attribute(destination, "TestPerson", "height", optional=False)
        source = base.duplicate()
        _set_attribute(source, "TestCar", "nbr_seats", optional=False)

        candidate = _candidate(base=base, destination=destination, source=source)

        assert candidate.get(name="TestPerson").get_attribute(name="height").optional is False
        assert candidate.get(name="TestCar").get_attribute(name="nbr_seats").optional is False

    def test_keeps_a_kind_changed_on_the_destination_only(self, base: SchemaBranch) -> None:
        destination = base.duplicate()
        car = destination.get(name="TestCar")
        nbr_seats = car.get_attribute(name="nbr_seats").model_dump(exclude={"parameters"})
        car.attributes = [
            TextAttributeSchema.model_validate({**nbr_seats, "kind": "Text"})
            if attribute.name == "nbr_seats"
            else attribute
            for attribute in car.attributes
        ]
        destination.set(name="TestCar", schema=car)
        source = base.duplicate()
        _set_attribute(source, "TestCar", "color", description="Color of the car")

        candidate = _candidate(base=base, destination=destination, source=source)

        car = candidate.get(name="TestCar")
        nbr_seats_candidate = car.get_attribute(name="nbr_seats")
        assert nbr_seats_candidate.kind == "Text"
        assert isinstance(nbr_seats_candidate.parameters, TextAttributeParameters)
        assert car.get_attribute(name="color").description == "Color of the car"

    def test_rebuilds_an_attribute_whose_kind_changed_on_the_source(self, base: SchemaBranch) -> None:
        destination = base.duplicate()
        _set_attribute(destination, "TestCar", "nbr_seats", description="Set on the destination")
        source = base.duplicate()
        car = source.get(name="TestCar")
        nbr_seats = car.get_attribute(name="nbr_seats").model_dump(exclude={"parameters"})
        car.attributes = [
            TextAttributeSchema.model_validate({**nbr_seats, "kind": "Text"})
            if attribute.name == "nbr_seats"
            else attribute
            for attribute in car.attributes
        ]
        source.set(name="TestCar", schema=car)

        candidate = _candidate(base=base, destination=destination, source=source)

        nbr_seats_candidate = candidate.get(name="TestCar").get_attribute(name="nbr_seats")
        assert nbr_seats_candidate.kind == "Text"
        assert isinstance(nbr_seats_candidate, TextAttributeSchema)
        assert isinstance(nbr_seats_candidate.parameters, TextAttributeParameters)
        assert nbr_seats_candidate.description == "Set on the destination"

    def test_applies_the_value_of_the_source_when_both_branches_change_a_property(self, base: SchemaBranch) -> None:
        destination = base.duplicate()
        _set_attribute(destination, "TestPerson", "height", description="Set on the destination")
        source = base.duplicate()
        _set_attribute(source, "TestPerson", "height", description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        assert candidate.get(name="TestPerson").get_attribute(name="height").description == "Set on the source"

    def test_keeps_the_attributes_added_on_either_branch(self, base: SchemaBranch) -> None:
        destination = base.duplicate()
        person = destination.get(name="TestPerson")
        person.attributes.append(AttributeSchema(name="nickname", kind="Text", optional=False))
        destination.set(name="TestPerson", schema=person)
        source = base.duplicate()
        person = source.get(name="TestPerson")
        person.attributes.append(AttributeSchema(name="badge", kind="Text", optional=True))
        source.set(name="TestPerson", schema=person)

        candidate = _candidate(base=base, destination=destination, source=source)

        person = candidate.get(name="TestPerson")
        assert sorted(person.attribute_names) == sorted(
            [*base.get(name="TestPerson").attribute_names, "badge", "nickname"]
        )
        assert person.get_attribute(name="nickname").optional is False
        assert person.get_attribute(name="badge").optional is True

    def test_leaves_out_an_attribute_removed_on_the_destination_and_unchanged_on_the_source(
        self, base: SchemaBranch
    ) -> None:
        destination = base.duplicate()
        person = destination.get(name="TestPerson")
        person.attributes = [attribute for attribute in person.attributes if attribute.name != "height"]
        destination.set(name="TestPerson", schema=person)
        source = base.duplicate()
        _set_attribute(source, "TestPerson", "name", description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        person = candidate.get(name="TestPerson")
        assert "height" not in person.attribute_names
        assert person.get_attribute(name="name").description == "Set on the source"

    def test_leaves_out_a_kind_removed_on_the_destination_and_unchanged_on_the_source(self, base: SchemaBranch) -> None:
        tag_root = SchemaRoot(
            nodes=[NodeSchema(name="Tag", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text")])]
        )
        base.load_schema(schema=tag_root)
        base.process()
        destination = base.duplicate()
        destination.delete(name="TestTag")
        source = base.duplicate()
        _set_attribute(source, "TestPerson", "height", description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        assert candidate.has(name="TestTag") is False
        assert candidate.get(name="TestPerson").get_attribute(name="height").description == "Set on the source"

    def test_follows_an_attribute_renamed_on_the_destination(self, base: SchemaBranch) -> None:
        _set_attribute(base, "TestPerson", "height", id="person-height-id")
        destination = base.duplicate()
        _set_attribute(destination, "TestPerson", "height", name="size")
        source = base.duplicate()
        _set_attribute(source, "TestPerson", "height", description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        person = candidate.get(name="TestPerson")
        assert "height" not in person.attribute_names
        size = person.get_attribute(name="size")
        assert size.id == "person-height-id"
        assert size.description == "Set on the source"

    def test_keeps_the_change_the_destination_made_to_an_inherited_attribute(
        self, car_person_schema_root: SchemaRoot
    ) -> None:
        base = _load_processed_branch(
            schema_root=_with_vehicle_generic(car_person_schema_root, wheels_description="Number of wheels")
        )
        destination = _load_processed_branch(
            schema_root=_with_vehicle_generic(car_person_schema_root, wheels_description="Set on the destination")
        )
        source = base.duplicate()
        _set_attribute(source, "TestCar", "color", description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        car = candidate.get(name="TestCar")
        assert car.get_attribute(name="wheels").inherited is True
        assert car.get_attribute(name="wheels").description == "Set on the destination"
        assert car.get_attribute(name="color").description == "Set on the source"
        assert candidate.get(name="TestVehicle").get_attribute(name="wheels").description == "Set on the destination"

    def test_applies_the_change_of_a_node_to_its_profile_kind(
        self, base: SchemaBranch, car_person_schema_root: SchemaRoot
    ) -> None:
        source_root = car_person_schema_root.model_copy(deep=True)
        source_car = next(node for node in source_root.nodes if node.name == "Car")
        source_car.get_attribute(name="color").description = "Set on the source"
        source = _load_processed_branch(schema_root=source_root)
        destination = base.duplicate()
        _set_attribute(destination, "TestPerson", "height", description="Set on the destination")

        candidate = _candidate(base=base, destination=destination, source=source)

        assert base.get(name="ProfileTestCar").get_attribute(name="color").description is None
        assert candidate.get(name="ProfileTestCar").get_attribute(name="color").description == "Set on the source"
        assert candidate.get(name="TestCar").get_attribute(name="color").description == "Set on the source"
        assert candidate.get(name="TestPerson").get_attribute(name="height").description == "Set on the destination"

    def test_keeps_the_source_version_of_an_attribute_removed_on_the_destination_and_changed_on_the_source(
        self, base: SchemaBranch
    ) -> None:
        destination = base.duplicate()
        person = destination.get(name="TestPerson")
        person.attributes = [attribute for attribute in person.attributes if attribute.name != "height"]
        destination.set(name="TestPerson", schema=person)
        source = base.duplicate()
        _set_attribute(source, "TestPerson", "height", optional=False, description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        height = candidate.get(name="TestPerson").get_attribute(name="height")
        assert height.optional is False
        assert height.description == "Set on the source"

    def test_keeps_the_source_version_of_a_kind_removed_on_the_destination_and_changed_on_the_source(
        self, base: SchemaBranch
    ) -> None:
        tag_root = SchemaRoot(
            nodes=[NodeSchema(name="Tag", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text")])]
        )
        base.load_schema(schema=tag_root)
        base.process()
        destination = base.duplicate()
        destination.delete(name="TestTag")
        source = base.duplicate()
        _set_attribute(source, "TestTag", "name", optional=False, description="Set on the source")

        candidate = _candidate(base=base, destination=destination, source=source)

        name = candidate.get(name="TestTag").get_attribute(name="name")
        assert name.optional is False
        assert name.description == "Set on the source"
        assert candidate.has(name="ProfileTestTag") is True

    def test_lists_the_nodes_both_branches_added_in_the_used_by_of_a_generic(
        self, car_person_schema_root: SchemaRoot
    ) -> None:
        base_root = _with_vehicle_generic(car_person_schema_root, wheels_description="Number of wheels")
        base = _load_processed_branch(schema_root=base_root)
        destination = _load_processed_branch(schema_root=_with_vehicle_nodes(base_root, names=["Truck"]))
        source = _load_processed_branch(schema_root=_with_vehicle_nodes(base_root, names=["Bike"]))

        candidate = _candidate(base=base, destination=destination, source=source)

        assert candidate.get_generic(name="TestVehicle").used_by == ["TestBike", "TestCar", "TestTruck"]
        assert {"ProfileTestBike", "ProfileTestTruck"} <= set(candidate.get_generic(name="CoreProfile").used_by)

    def test_leaves_out_of_the_used_by_of_a_generic_the_nodes_either_branch_removed(
        self, car_person_schema_root: SchemaRoot
    ) -> None:
        vehicle_root = _with_vehicle_generic(car_person_schema_root, wheels_description="Number of wheels")
        base = _load_processed_branch(schema_root=_with_vehicle_nodes(vehicle_root, names=["Bike", "Truck"]))
        destination = _load_processed_branch(schema_root=_with_vehicle_nodes(vehicle_root, names=["Bike"]))
        source = _load_processed_branch(schema_root=_with_vehicle_nodes(vehicle_root, names=["Truck"]))

        candidate = _candidate(base=base, destination=destination, source=source)

        assert candidate.get_generic(name="TestVehicle").used_by == ["TestCar"]
