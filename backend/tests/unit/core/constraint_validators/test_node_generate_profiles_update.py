from itertools import chain

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.generate_profile import NodeGenerateProfileChecker
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("generate_profile", [True, False])
async def test_set_generate_profile_success(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, generate_profile
):
    branch = await create_branch(branch_name="branch", db=db)
    updated_schema = registry.schema.get_node_schema(name="TestCar")
    updated_schema.generate_profile = generate_profile
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    assert len(list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))) == 0


async def test_set_generate_profile_false_fail(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    branch = await create_branch(branch_name="branch", db=db)
    profile_schema = registry.schema.get(name="ProfileTestCar", branch=branch)
    profile_node = await Node.init(db=db, schema=profile_schema, branch=branch)
    await profile_node.new(db=db, profile_name="bus", nbr_seats=50)
    await profile_node.save(db=db)
    updated_schema = registry.schema.get_node_schema(name="TestCar")
    updated_schema.generate_profile = False
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 1
    assert all_data_paths[0] == DataPath(
        branch=branch.name, path_type=PathType.NODE, node_id=profile_node.id, kind="ProfileTestCar"
    )


async def test_set_generate_profile_false_branch_delete_profile_success(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema
):
    profile_schema = registry.schema.get(name="ProfileTestCar", branch=default_branch)
    profile_node = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile_node.new(db=db, profile_name="bus", nbr_seats=50)
    await profile_node.save(db=db)
    branch = await create_branch(branch_name="branch", db=db)
    profile_node_branch = await NodeManager.get_one(db=db, branch=branch, id=profile_node.id)
    await profile_node_branch.delete(db=db)
    updated_schema = registry.schema.get_node_schema(name="TestCar")
    updated_schema.generate_profile = False
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 0
