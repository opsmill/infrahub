"""Combining the schema comparison with the data diff, against a real branch diff.

The unrestricted constraint the schema comparison produces has to survive being merged with the
node-scoped ones a real data diff produces, including those the schema edit itself contributes as
data.
"""

from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry

CAR_KIND = "TestCar"
PERSON_KIND = "TestPerson"


async def _persist_base_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Write the car/person schema to the database so a later branch can be compared against it."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(
        db=db, branch=default_branch, schema=schema, limit=[CAR_KIND, PERSON_KIND], update_db=True
    )


async def _change_attribute_parameter(
    db: InfrahubDatabase, branch: Branch, node_kind: str, attribute_name: str, **changes: Any
) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    node_schema = schema.get(name=node_kind)
    attribute = node_schema.get_attribute(name=attribute_name)
    for name, value in changes.items():
        setattr(attribute.parameters, name, value)
    schema.set(name=node_kind, schema=node_schema)
    schema.process()
    await registry.schema.update_schema_branch(db=db, branch=branch, schema=schema, limit=[node_kind], update_db=True)


async def test_the_schema_constraint_survives_merging_with_the_data_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main: Node,
) -> None:
    """The node-scoped constraints a data change contributes must not narrow the schema comparison's."""
    await _persist_base_schema(db=db, default_branch=default_branch)
    branch = await create_branch(db=db, branch_name="regex-with-data-change")

    person = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch, raise_on_error=True)
    person.get_attribute("height").value = 190
    await person.save(db=db)

    await _change_attribute_parameter(
        db=db, branch=branch, node_kind=PERSON_KIND, attribute_name="name", regex=r"^[A-Z][a-z]+$"
    )

    component_registry = get_component_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    node_field_summaries = await diff_repository.get_node_field_summaries(
        diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name)
    )

    analyzer = MergeSchemaAnalyzer(
        db=db,
        source_branch=branch,
        destination_branch=default_branch,
        diff_repository=diff_repository,
        schema_manager=registry.schema,
    )
    candidate_schema = await analyzer.get_candidate_schema()
    schema_constraints = await analyzer.calculate_validations(target_schema=candidate_schema)

    determiner = build_constraint_validator_determiner(db=db, branch=branch)
    data_constraints = await determiner.get_constraints(schema_branch=candidate_schema, node_diffs=node_field_summaries)
    merged = build_constraint_info_merger().merge(candidate_schema, data_constraints, schema_constraints)

    expected = SchemaUpdateConstraintInfo(
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE,
            schema_kind=PERSON_KIND,
            field_name="name",
            property_name="parameters.regex",
        ),
    )

    assert {c for c in schema_constraints if c.path.schema_kind == PERSON_KIND} == {expected}
    assert {c.node_uuids for c in schema_constraints} == {None}
    assert {c for c in merged if c.constraint_name == expected.constraint_name} == {expected}
