import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PathType, SchemaPathType
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.number_pool import (
    AttributeNumberPoolChecker,
    AttributeNumberPoolUpdateValidatorQuery,
)
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


@pytest.fixture
async def snow_incident_01(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Node:
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    snps = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema)
    await snps.run()

    incident_1 = await Node.init(db=db, schema="SnowIncident", branch=default_branch)
    await incident_1.new(db=db, title="The first issue")
    await incident_1.save(db=db)

    return incident_1


@pytest.mark.parametrize("start_range,end_range", [(1, 500), (-20, 50)])
async def test_query_numberpool_constraints_success(
    db: InfrahubDatabase, default_branch: Branch, snow_incident_01: Node, start_range: int, end_range: int
) -> None:
    incident_schema = registry.schema.get(name="SnowIncident")
    number = incident_schema.get_attribute(name="number")
    assert isinstance(number.parameters, NumberPoolParameters)
    number.parameters.start_range = start_range
    number.parameters.end_range = end_range

    node_schema = incident_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="SnowIncident", field_name="number")

    query = await AttributeNumberPoolUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_numberpool_constraints_too_small(
    db: InfrahubDatabase, default_branch: Branch, snow_incident_01: Node
) -> None:
    incident_schema = registry.schema.get(name="SnowIncident")
    number = incident_schema.get_attribute(name="number")
    assert isinstance(number.parameters, NumberPoolParameters)
    number.parameters.start_range = 10
    number.parameters.end_range = 20

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="SnowIncident", field_name="number")

    query = await AttributeNumberPoolUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=incident_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=snow_incident_01.id,
            kind="SnowIncident",
            field_name="number",
            value=1,
        )
        in all_data_paths
    )


async def test_query_numberpool_constraints_too_large(
    db: InfrahubDatabase, default_branch: Branch, snow_incident_01: Node
) -> None:
    incident_schema = registry.schema.get(name="SnowIncident")
    number = incident_schema.get_attribute(name="number")
    assert isinstance(number.parameters, NumberPoolParameters)
    number.parameters.start_range = -20
    number.parameters.end_range = -10

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="SnowIncident", field_name="number")

    query = await AttributeNumberPoolUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=incident_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=snow_incident_01.id,
            kind="SnowIncident",
            field_name="number",
            value=1,
        )
        in all_data_paths
    )


async def test_validator_range(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    snow_incident_01: Node,
) -> None:
    await branch.rebase(db=db)

    """
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = 100
    height_attr.parameters.max_value = 150
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)
    """
    incident_schema = registry.schema.get_node_schema(name="SnowIncident")
    number = incident_schema.get_attribute(name="number")
    assert isinstance(number.parameters, NumberPoolParameters)
    number.parameters.start_range = -5
    number.parameters.end_range = 5
    registry.schema.set(name="SnowIncident", schema=incident_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value,
        node_schema=incident_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="SnowIncident", field_name="number"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeNumberPoolChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)
    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 0

    number.parameters.start_range = 100
    number.parameters.end_range = 200
    registry.schema.set(name="SnowIncident", schema=incident_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value,
        node_schema=incident_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="SnowIncident", field_name="number"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeNumberPoolChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=snow_incident_01.id,
            kind="SnowIncident",
            field_name="number",
            value=1,
        )
        in data_paths
    )
