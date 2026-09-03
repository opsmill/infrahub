"""Combining the schema comparison with the data diff, against a real branch diff.

The unrestricted constraint the schema comparison produces has to survive being merged with the
node-scoped ones a real data diff produces, including those the schema edit itself contributes as
data.

Both routes into the schema comparison are covered: a property flagged ``validate_constraint``
becomes a constraint directly, while one flagged ``migration_required`` becomes a migration and is
only turned back into a constraint where a checker exists for it.
"""

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.merge import build_schema_analyzer, set_attribute, set_attribute_parameters

CAR_KIND = "TestCar"
PERSON_KIND = "TestPerson"


def _attribute_constraint(
    kind: str, field_name: str, property_name: str, constraint_name: str
) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=constraint_name,
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE,
            schema_kind=kind,
            field_name=field_name,
            property_name=property_name,
        ),
    )


async def _persist_base_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Write the car/person schema to the database so a later branch can be compared against it."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(
        db=db, branch=default_branch, schema=schema, limit=[CAR_KIND, PERSON_KIND], update_db=True
    )


async def test_both_schema_routes_survive_merging_with_the_data_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main: Node,
) -> None:
    """The node-scoped constraints a data change contributes must not narrow the schema comparison's.

    The branch changes a directly-constrained property on one kind and a migration-gated one on
    another, and edits instance data for both, so each route is checked against the same merge.
    """
    await _persist_base_schema(db=db, default_branch=default_branch)
    branch = await create_branch(db=db, branch_name="schema-and-data-change")

    person = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch, raise_on_error=True)
    person.get_attribute("height").value = 190
    await person.save(db=db)

    car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch, raise_on_error=True)
    car.get_attribute("color").value = "#111111"
    await car.save(db=db)

    await set_attribute_parameters(
        db=db, branch=branch, node_kind=PERSON_KIND, attribute_name="name", regex=r"^[A-Z][a-z]+$"
    )
    await set_attribute(db=db, branch=branch, node_kind=CAR_KIND, attribute_name="color", kind="TextArea")

    component_registry = get_component_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    node_field_summaries = await diff_repository.get_node_field_summaries(
        diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name)
    )

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    candidate_schema = await analyzer.get_candidate_schema()
    schema_constraints = await analyzer.calculate_validations(target_schema=candidate_schema)

    determiner = build_constraint_validator_determiner(db=db, branch=branch)
    data_constraints = await determiner.get_constraints(schema_branch=candidate_schema, node_diffs=node_field_summaries)
    merged = build_constraint_info_merger().merge(candidate_schema, data_constraints, schema_constraints)

    regex = _attribute_constraint(
        kind=PERSON_KIND,
        field_name="name",
        property_name="parameters.regex",
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
    )
    kind = _attribute_constraint(
        kind=CAR_KIND, field_name="color", property_name="kind", constraint_name="attribute.kind.update"
    )
    hierarchical = SchemaUpdateConstraintInfo(
        constraint_name="node.hierarchical.update",
        path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind="CoreGroup",
            field_name="hierarchical",
            property_name="hierarchical",
        ),
    )

    assert set(schema_constraints) == {regex, kind, hierarchical}
    assert {c.node_uuids for c in schema_constraints} == {None}

    # merging constraints cannot drop a constraint or narrow its scope.
    schema_side = {regex, kind, hierarchical}
    assert schema_side <= set(merged)
    assert {c.node_uuids for c in merged if c in schema_side} == {None}
