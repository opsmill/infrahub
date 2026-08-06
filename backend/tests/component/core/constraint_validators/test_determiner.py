import logging

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDirection, SchemaPathType
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.node_diff_index import NodeDiffIndex
from infrahub.core.validators.uniqueness.scope import UniquenessConstraintScoper

RELATIONSHIP_PROPERTIES = ("peer", "cardinality", "optional", "min_count", "max_count")

# uuids of the changed nodes carried by the test node-diffs, so a uniqueness check emitted for a
# directly-changed kind can be asserted to be scoped to exactly those nodes
CHANGED_PERSON_UUID = "person-1"
CHANGED_ELECTRIC_CAR_UUID = "electric-car-1"


class _NoDependentsResolver:
    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]:
        return set()


def _build_determiner() -> ConstraintValidatorDeterminer:
    node_diff_index = NodeDiffIndex()
    scoper = UniquenessConstraintScoper(dependent_resolver=_NoDependentsResolver(), node_diff_index=node_diff_index)
    return ConstraintValidatorDeterminer(node_diff_index=node_diff_index, uniqueness_scoper=scoper)


def node_constraint(kind: str, property_name: str) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=f"node.{property_name}.update",
        path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind=kind,
            field_name=property_name,
            property_name=property_name,
        ),
    )


def node_uniqueness_constraint(kind: str, node_uuids: list[str] | None = None) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name="node.uniqueness_constraints.update",
        path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind=kind,
            field_name="uniqueness_constraints",
            property_name="uniqueness_constraints",
        ),
        node_uuids=node_uuids,
    )


def attribute_constraint(kind: str, field_name: str, property_name: str) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=f"attribute.{property_name}.update",
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE,
            schema_kind=kind,
            field_name=field_name,
            property_name=property_name,
        ),
    )


def relationship_constraint(kind: str, field_name: str, property_name: str) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=f"relationship.{property_name}.update",
        path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP,
            schema_kind=kind,
            field_name=field_name,
            property_name=property_name,
        ),
    )


@pytest.fixture
def person_name_node_diff(
    person_john_main: Node, default_branch: Branch
) -> tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]]:
    node_diff = NodeDiffFieldSummary(kind="TestPerson", attribute_node_uuids={"name": {CHANGED_PERSON_UUID}})
    schema_updated_constraint_infos = {
        SchemaUpdateConstraintInfo(
            path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE,
                schema_kind="TestPerson",
                schema_id=None,
                field_name="name",
                property_name="kind",
            ),
            constraint_name="attribute.kind.update",
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.optional.update",
            path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE,
                schema_kind="TestPerson",
                field_name="name",
                property_name="optional",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.unique.update",
            path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE,
                schema_kind="TestPerson",
                field_name="name",
                property_name="unique",
            ),
        ),
    }
    return node_diff, schema_updated_constraint_infos


@pytest.fixture
def person_cars_node_diff(
    person_john_main: Node, default_branch: Branch
) -> tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]]:
    node_diff = NodeDiffFieldSummary(kind="TestPerson", relationship_node_uuids={"cars": set()})
    schema_updated_constraint_infos = {
        SchemaUpdateConstraintInfo(
            constraint_name="relationship.min_count.update",
            path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP,
                schema_kind="TestPerson",
                field_name="cars",
                property_name="min_count",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="relationship.max_count.update",
            path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP,
                schema_kind="TestPerson",
                field_name="cars",
                property_name="max_count",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="relationship.peer.update",
            path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP,
                schema_kind="TestPerson",
                field_name="cars",
                property_name="peer",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="relationship.cardinality.update",
            path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP,
                schema_kind="TestPerson",
                field_name="cars",
                property_name="cardinality",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="relationship.optional.update",
            path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP,
                schema_kind="TestPerson",
                field_name="cars",
                property_name="optional",
            ),
        ),
    }
    return node_diff, schema_updated_constraint_infos


class TestConstraintDeterminer:
    async def test_no_node_diffs(self, car_person_schema: SchemaBranch, default_branch: Branch) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[])

        assert constraints == []

    async def test_one_attribute_update_node_diff(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_name_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_name_node_diff

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        relevant_constraints = [
            c
            for c in constraints
            if c.constraint_name not in ["node.generate_profile.update", "node.uniqueness_constraints.update"]
            and c.path.schema_kind in ["TestCar", "TestPerson"]
        ]
        assert len(relevant_constraints) == len(constraint_info_set)
        assert set(relevant_constraints) == constraint_info_set

    async def test_many_relationship_update(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_cars_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_cars_node_diff

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert len(constraints) == len(constraint_info_set)
        assert constraint_info_set == set(constraints)

    async def test_node_property_constraints_included(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_name_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person_schema = schema_branch.get(name="TestPerson", duplicate=False)
        person_schema.uniqueness_constraints = [["name", "height"]]
        name_attr_schema = person_schema.get_attribute("name")
        name_attr_schema.parameters.max_length = 30
        car_schema = schema_branch.get(name="TestCar", duplicate=False)
        car_schema.uniqueness_constraints = [["owner", "color__value"]]
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_name_node_diff
        max_length_param_constraint_info = SchemaUpdateConstraintInfo(
            constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MAX_LENGTH_UPDATE.value,
            path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE,
                schema_kind="TestPerson",
                field_name="name",
                property_name="parameters.max_length",
            ),
        )
        constraint_info_set.add(node_uniqueness_constraint("TestPerson", node_uuids=[CHANGED_PERSON_UUID]))
        constraint_info_set.add(max_length_param_constraint_info)

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert set(constraints) == constraint_info_set

    async def test_uniqueness_constraint_on_peer_attribute_included(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_name_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        car_schema = schema_branch.get(name="TestCar", duplicate=False)
        car_schema.uniqueness_constraints = [["owner__name", "color__value"]]
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_name_node_diff
        constraint_info_set.add(node_uniqueness_constraint("TestPerson", node_uuids=[CHANGED_PERSON_UUID]))
        # TestCar's constraint reads the name attribute of the related TestPerson, so a TestPerson
        # data change can violate it even though TestCar itself has no diff.
        constraint_info_set.add(node_uniqueness_constraint("TestCar"))

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert set(constraints) == constraint_info_set

    async def test_uniqueness_not_triggered_by_unrelated_field(
        self,
        car_person_schema_generics_simple: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        generic_schema = schema_branch.get(name="TestCar", duplicate=False)
        generic_schema.uniqueness_constraints = [["name__value"]]
        determiner = _build_determiner()
        node_diff = NodeDiffFieldSummary(kind="TestElectricCar", attribute_node_uuids={"nbr_engine": set()})
        # nbr_engine participates in no uniqueness path, so the uniqueness check must not be
        # triggered on the implementation or on its generic; only the nbr_engine field constraints remain
        constraint_info_set = {
            attribute_constraint("TestElectricCar", "nbr_engine", "kind"),
            attribute_constraint("TestElectricCar", "nbr_engine", "optional"),
            attribute_constraint("TestElectricCar", "nbr_engine", "unique"),
        }

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert set(constraints) == constraint_info_set

    async def test_generic_uniqueness_triggered_by_inherited_field(
        self,
        car_person_schema_generics_simple: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        generic_schema = schema_branch.get(name="TestCar", duplicate=False)
        generic_schema.uniqueness_constraints = [["name__value"]]
        determiner = _build_determiner()
        # `name` is inherited from the generic; a generic-level uniqueness check spans every
        # implementing node, so changing name on an implementation must trigger the check on the
        # generic (TestCar) as well as on the implementation (TestElectricCar)
        node_diff = NodeDiffFieldSummary(
            kind="TestElectricCar", attribute_node_uuids={"name": {CHANGED_ELECTRIC_CAR_UUID}}
        )

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        # both the generic and the implementation checks are scoped to the changed implementation node
        expected = {
            node_uniqueness_constraint("TestCar", node_uuids=[CHANGED_ELECTRIC_CAR_UUID]),
            node_uniqueness_constraint("TestElectricCar", node_uuids=[CHANGED_ELECTRIC_CAR_UUID]),
            attribute_constraint("TestElectricCar", "name", "kind"),
            attribute_constraint("TestElectricCar", "name", "optional"),
            attribute_constraint("TestElectricCar", "name", "unique"),
        }
        assert set(constraints) == expected

    async def test_uniqueness_triggered_by_generic_peer_implementation(
        self,
        hierarchical_location_schema_simple: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        thing_schema = schema_branch.get(name="TestThing", duplicate=False)
        # TestThing.location (cardinality one) points to the generic LocationGeneric; a constraint
        # reading the peer's `name` must fire when an implementation of that generic (LocationSite)
        # changes `name`, even though the peer kind named in the path (LocationGeneric) has no diff
        thing_schema.uniqueness_constraints = [["location__name"]]
        determiner = _build_determiner()
        node_diff = NodeDiffFieldSummary(kind="LocationSite", attribute_node_uuids={"name": set()})

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert node_uniqueness_constraint("TestThing") in set(constraints)

    async def test_uniqueness_not_triggered_by_unrelated_peer_attribute(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        car_schema = schema_branch.get(name="TestCar", duplicate=False)
        car_schema.uniqueness_constraints = [["owner__name", "color__value"]]
        determiner = _build_determiner()
        # TestCar's uniqueness constraints read TestPerson.name; a change to an unrelated
        # TestPerson attribute, height, does not participate, so neither kind's uniqueness
        # check should trigger
        node_diff = NodeDiffFieldSummary(kind="TestPerson", attribute_node_uuids={"height": set()})

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        constraint_set = set(constraints)
        assert node_uniqueness_constraint("TestCar") not in constraint_set
        assert node_uniqueness_constraint("TestPerson") not in constraint_set

    async def test_kind_missing_from_schema_is_skipped(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_name_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_name_node_diff
        constraint_info_set.add(node_uniqueness_constraint("TestPerson", node_uuids=[CHANGED_PERSON_UUID]))

        constraints = await determiner.get_constraints(
            schema_branch=schema_branch,
            node_diffs=[NodeDiffFieldSummary(kind="TestDeleted", attribute_node_uuids={"name": set()}), node_diff],
        )

        # TestDeleted is absent from the schema, so it contributes nothing; only TestPerson remains
        assert set(constraints) == constraint_info_set

    async def test_internal_schema_kinds_only_when_in_diff(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        person_name_node_diff: tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]],
    ) -> None:
        schema_branch = registry.schema.register_schema(
            schema=SchemaRoot(**internal_schema), branch=default_branch.name
        )
        determiner = _build_determiner()
        node_diff, constraint_info_set = person_name_node_diff
        constraint_info_set.add(node_uniqueness_constraint("TestPerson", node_uuids=[CHANGED_PERSON_UUID]))

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])
        # internal schema kinds are absent from the diff, so none contribute constraints
        assert set(constraints) == constraint_info_set

        internal_kinds = {"SchemaNode", "SchemaGeneric", "SchemaAttribute", "SchemaRelationship"}
        determiner = _build_determiner()
        constraints = await determiner.get_constraints(
            schema_branch=schema_branch,
            node_diffs=[
                node_diff,
                *(NodeDiffFieldSummary(kind=kind, attribute_node_uuids={"name": set()}) for kind in internal_kinds),
            ],
        )
        # once an internal schema kind is in the diff, its uniqueness constraint must be validated
        # (this is what catches duplicate schema elements when a branch is merged)
        for kind in internal_kinds:
            assert node_uniqueness_constraint(kind) in set(constraints)
        assert {c.path.schema_kind for c in constraints} == {"TestPerson", *internal_kinds}

    async def test_hierarchy_constraints_selected_for_both_endpoint_kinds(
        self,
        hierarchical_location_schema_simple: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()
        # A hierarchy edge change surfaces on both endpoints: the child (LocationRack) records its
        # `parent` change and the parent (LocationSite) records its `children` change. Each endpoint
        # emits only the hierarchy constraint whose relationship actually changed there, and no
        # uniqueness constraint since `name` (the only unique field) is not in the diff.
        node_diffs = [
            NodeDiffFieldSummary(kind="LocationRack", relationship_node_uuids={"parent": set()}),
            NodeDiffFieldSummary(kind="LocationSite", relationship_node_uuids={"children": set()}),
        ]
        expected = {
            node_constraint("LocationRack", "parent"),
            node_constraint("LocationSite", "children"),
            *(relationship_constraint("LocationRack", "parent", p) for p in RELATIONSHIP_PROPERTIES),
            *(relationship_constraint("LocationSite", "children", p) for p in RELATIONSHIP_PROPERTIES),
        }

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=node_diffs)

        assert set(constraints) == expected

    async def test_unparseable_uniqueness_constraint_element_is_skipped_and_logged(
        self,
        car_person_schema: SchemaBranch,
        default_branch: Branch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person_schema = schema_branch.get(name="TestPerson", duplicate=False)
        person_schema.uniqueness_constraints = [["does_not_exist__value"]]
        determiner = _build_determiner()
        # `height` is not a unique attribute, so evaluating uniqueness must fall through to parsing
        # the (unparseable) constraint group rather than short-circuiting on a unique attribute.
        node_diff = NodeDiffFieldSummary(kind="TestPerson", attribute_node_uuids={"height": set()})

        with caplog.at_level(logging.WARNING):
            constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=[node_diff])

        assert "Cannot parse TestPerson.uniqueness_constraints element 'does_not_exist__value'" in caplog.text
        # the unparseable element is skipped in isolation, so no uniqueness check is emitted for the kind
        assert node_uniqueness_constraint("TestPerson") not in set(constraints)

    async def test_hierarchy_constraint_scoped_to_changed_relationship(
        self,
        hierarchical_location_schema_simple: SchemaRoot,
        default_branch: Branch,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = _build_determiner()
        # Re-parenting a rack changes only its `parent` relationship, so only the parent hierarchy
        # constraint may be emitted for that kind, never the children one.
        node_diffs = [NodeDiffFieldSummary(kind="LocationSite", relationship_node_uuids={"parent": set()})]

        constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=node_diffs)

        constraint_set = set(constraints)
        assert node_constraint("LocationSite", "parent") in constraint_set
        assert node_constraint("LocationSite", "children") not in constraint_set
        assert node_uniqueness_constraint("LocationSite") not in constraint_set
