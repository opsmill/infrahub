from dataclasses import dataclass
from itertools import chain

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.generate_profile import NodeGenerateProfileChecker
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("generate_profile", [True, False])
async def test_set_generate_profile_success(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, generate_profile: bool
) -> None:
    branch = await create_branch(branch_name="branch", db=db)
    updated_schema = registry.schema.get_node_schema(name="TestCar")
    updated_schema.generate_profile = generate_profile
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    assert len(list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))) == 0


@pytest.mark.parametrize("generate_profile", [True, False])
async def test_set_generate_profile_success_generics(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch, generate_profile: bool
) -> None:
    branch = await create_branch(branch_name="branch", db=db)
    updated_schema = registry.schema.get(name="TestAnimal")
    updated_schema.generate_profile = generate_profile
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestAnimal"),
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    assert len(list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))) == 0


async def test_set_generate_profile_false_fail(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
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
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 1
    assert all_data_paths[0] == DataPath(
        branch=branch.name, path_type=PathType.NODE, node_id=profile_node.id, kind="ProfileTestCar"
    )


async def test_set_generate_profile_false_fail_generic(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    branch = await create_branch(branch_name="branch", db=db)
    profile_schema = registry.schema.get(name="ProfileTestAnimal", branch=branch)
    profile_node = await Node.init(db=db, schema=profile_schema, branch=branch)
    await profile_node.new(db=db, profile_name="chupacabra")
    await profile_node.save(db=db)
    updated_schema = registry.schema.get(name="TestAnimal")
    updated_schema.generate_profile = False
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=updated_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestAnimal"),
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 1
    assert all_data_paths[0] == DataPath(
        branch=branch.name, path_type=PathType.NODE, node_id=profile_node.id, kind="ProfileTestAnimal"
    )


async def test_set_generate_profile_false_branch_delete_profile_success(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
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
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    checker = NodeGenerateProfileChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 0


@dataclass(frozen=True)
class ViewCase:
    name: str
    is_isolated: bool
    expected_profiles: list[str]


VIEW_CASES = [
    ViewCase(name="branch-view", is_isolated=True, expected_profiles=["created_on_main_before_branch"]),
    ViewCase(
        name="merge-view",
        is_isolated=False,
        expected_profiles=["created_on_main_before_branch", "created_on_main_after_branch"],
    ),
]


@pytest.mark.parametrize("case", VIEW_CASES, ids=lambda case: case.name)
async def test_validator_on_branch_reads_the_requested_view_of_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, case: ViewCase
) -> None:
    profile_schema = registry.schema.get(name="ProfileTestCar", branch=default_branch)
    created_on_main_before_branch = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await created_on_main_before_branch.new(db=db, profile_name="bus", nbr_seats=50)
    await created_on_main_before_branch.save(db=db)
    branch = await create_branch(db=db, branch_name="branch-removes-profiles")
    created_on_main_after_branch = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await created_on_main_after_branch.new(db=db, profile_name="van", nbr_seats=8)
    await created_on_main_after_branch.save(db=db)
    profiles = {
        "created_on_main_before_branch": created_on_main_before_branch,
        "created_on_main_after_branch": created_on_main_after_branch,
    }

    car_schema = registry.schema.get_node_schema(name="TestCar", branch=branch).duplicate()
    car_schema.generate_profile = False
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.generate_profile.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
        schema_branch=SchemaBranch(cache={}, name="test"),
        is_isolated=case.is_isolated,
    )

    grouped_data_paths = await NodeGenerateProfileChecker(db=db, branch=branch).check(request=request)

    data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(data_paths) == len(case.expected_profiles)
    assert {data_path.node_id: data_path for data_path in data_paths} == {
        profiles[label].id: DataPath(
            branch=default_branch.name, path_type=PathType.NODE, node_id=profiles[label].id, kind="ProfileTestCar"
        )
        for label in case.expected_profiles
    }
