import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer


@pytest.fixture
def person_name_node_diff(
    person_john_main: Node, default_branch: Branch
) -> tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]]:
    node_diff = NodeDiffFieldSummary(kind="TestPerson", attribute_names={"name"})
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
        SchemaUpdateConstraintInfo(
            constraint_name="node.inherit_from.update",
            path=SchemaPath(
                path_type=SchemaPathType.NODE,
                schema_kind="TestPerson",
                field_name="inherit_from",
                property_name="inherit_from",
            ),
        ),
        SchemaUpdateConstraintInfo(
            constraint_name="node.inherit_from.update",
            path=SchemaPath(
                path_type=SchemaPathType.NODE,
                schema_kind="TestCar",
                field_name="inherit_from",
                property_name="inherit_from",
            ),
        ),
    }
    return node_diff, schema_updated_constraint_infos


@pytest.fixture
def person_cars_node_diff(
    person_john_main: Node, default_branch: Branch
) -> tuple[NodeDiffFieldSummary, set[SchemaUpdateConstraintInfo]]:
    node_diff = NodeDiffFieldSummary(kind="TestPerson", relationship_names={"cars"})
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
    async def test_no_node_diffs(self, car_person_schema, default_branch):
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = ConstraintValidatorDeterminer(schema_branch=schema_branch)

        constraints = await determiner.get_constraints(node_diffs=[])

        assert constraints == []

    async def test_one_attribute_update_node_diff(self, car_person_schema, default_branch, person_name_node_diff):
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = ConstraintValidatorDeterminer(schema_branch=schema_branch)
        node_diff, constraint_info_set = person_name_node_diff

        constraints = await determiner.get_constraints(node_diffs=[node_diff])

        relevant_constraints = [
            c
            for c in constraints
            if c.constraint_name not in ["node.generate_profile.update", "node.uniqueness_constraints.update"]
        ]
        assert len(relevant_constraints) == len(constraint_info_set)
        assert set(relevant_constraints) == constraint_info_set

    async def test_many_relationship_update(self, car_person_schema, default_branch, person_cars_node_diff):
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        determiner = ConstraintValidatorDeterminer(schema_branch=schema_branch)
        node_diff, constraint_info_set = person_cars_node_diff

        constraints = await determiner.get_constraints(node_diffs=[node_diff])

        assert len(constraints) >= len(constraint_info_set)
        assert constraint_info_set < set(constraints)

    async def test_node_property_constraints_included(self, car_person_schema, default_branch, person_name_node_diff):
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person_schema = schema_branch.get(name="TestPerson", duplicate=False)
        person_schema.uniqueness_constraints = [["name", "height"]]
        car_schema = schema_branch.get(name="TestCar", duplicate=False)
        car_schema.uniqueness_constraints = [["owner", "color__value"]]
        determiner = ConstraintValidatorDeterminer(schema_branch=schema_branch)
        node_diff, constraint_info_set = person_name_node_diff
        person_uniqueness_constraint_info = SchemaUpdateConstraintInfo(
            constraint_name="node.uniqueness_constraints.update",
            path=SchemaPath(
                path_type=SchemaPathType.NODE,
                schema_kind="TestPerson",
                field_name="uniqueness_constraints",
                property_name="uniqueness_constraints",
            ),
        )
        car_uniqueness_constraint_info = SchemaUpdateConstraintInfo(
            constraint_name="node.uniqueness_constraints.update",
            path=SchemaPath(
                path_type=SchemaPathType.NODE,
                schema_kind="TestCar",
                field_name="uniqueness_constraints",
                property_name="uniqueness_constraints",
            ),
        )
        constraint_info_set.add(person_uniqueness_constraint_info)
        constraint_info_set.add(car_uniqueness_constraint_info)

        constraints = await determiner.get_constraints(node_diffs=[node_diff])

        relevant_constraints = [
            c
            for c in constraints
            if c.constraint_name != "node.generate_profile.update" and c.path.schema_kind in {"TestCar", "TestPerson"}
        ]
        assert len(relevant_constraints) == len(constraint_info_set)
        assert set(relevant_constraints) == constraint_info_set
