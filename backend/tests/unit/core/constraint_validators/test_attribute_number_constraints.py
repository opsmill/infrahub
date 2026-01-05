import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.min_max import AttributeNumberChecker, AttributeNumberUpdateValidatorQuery
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("min_value,max_value", [(None, None), (None, 300), (1, None), (10, 300)])
async def test_query_number_constraints_success(
    db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main, min_value, max_value
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = min_value
    height_attr.parameters.max_value = max_value

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeNumberUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_number_constraints_too_small(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = 300
    height_attr.parameters.max_value = None

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeNumberUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in all_data_paths
    )


async def test_query_number_too_large(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = None
    height_attr.parameters.max_value = 10

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeNumberUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in all_data_paths
    )


async def test_query_update_on_branch(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
) -> None:
    person_john_main.height.value = 400
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    person_john.height.value = 180
    await person_john.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = 10
    height_attr.parameters.max_value = 300

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeNumberUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_delete_on_branch(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
) -> None:
    person_john_main.height.value = 200
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    await person_john.delete(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = 100
    height_attr.parameters.max_value = 150

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeNumberUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in all_data_paths
    )


async def test_validator_min_max(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
) -> None:
    await branch.rebase(db=db)
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.min_value = 100
    height_attr.parameters.max_value = 150
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value,
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeNumberChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in data_paths
    )


@pytest.mark.parametrize(
    "excluded_values",
    [
        "180",
        "170-180",
        "170-175,180-185,190-195, 200",
    ],
)
async def test_validator_excluded_values(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
    excluded_values: str,
) -> None:
    await branch.rebase(db=db)
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    height_attr = person_schema.get_attribute(name="height")
    height_attr.parameters.excluded_values = excluded_values
    height_attr.parameters.min_value = None
    height_attr.parameters.max_value = None
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value,
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeNumberChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="height",
            value=180,
        )
        in data_paths
    )


def test_get_excluded_values() -> None:
    parameters = NumberAttributeParameters(excluded_values="100")
    assert parameters.get_excluded_single_values() == [100]
    assert parameters.get_excluded_ranges() == []

    parameters = NumberAttributeParameters(excluded_values="100-200")
    assert parameters.get_excluded_ranges() == [(100, 200)]
    assert parameters.get_excluded_single_values() == []

    parameters = NumberAttributeParameters(excluded_values="100,150-200,280,300-400")
    assert parameters.get_excluded_single_values() == [100, 280]
    assert parameters.get_excluded_ranges() == [(150, 200), (300, 400)]

    with pytest.raises(ValueError):
        parameters = NumberAttributeParameters(excluded_values="100-")

    with pytest.raises(ValueError, match="Excluded ranges cannot overlap"):
        parameters = NumberAttributeParameters(excluded_values="100-200,150-250")

    with pytest.raises(ValueError, match="Excluded ranges cannot overlap"):
        parameters = NumberAttributeParameters(excluded_values="100-200,200-250")
