import copy
import uuid
from itertools import chain

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.inherit_from import NodeInheritFromChecker
from infrahub.database import InfrahubDatabase


async def test_add_generic_success(db: InfrahubDatabase, default_branch: Branch, animal_person_schema) -> None:
    branch = await create_branch(branch_name="branch", db=db)

    good_animal_schema = GenericSchema(
        name="GoodAnimal", namespace="Test", attributes=[{"name": "is_good", "kind": "Boolean", "default_value": True}]
    )
    dog_schema = registry.schema.get_node_schema(name="TestDog")
    dog_schema.inherit_from.append(good_animal_schema.kind)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.set(name=good_animal_schema.kind, schema=good_animal_schema)
    schema_branch.set(name=dog_schema.kind, schema=dog_schema)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.inherit_from.update",
        node_schema=dog_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestDog"),
        schema_branch=schema_branch,
    )

    checker = NodeInheritFromChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert len(all_data_paths) == 0


async def test_remove_generic_fail(db: InfrahubDatabase, default_branch: Branch, animal_person_schema) -> None:
    branch = await create_branch(branch_name="branch", db=db)

    dog_schema = registry.schema.get_node_schema(name="TestDog")
    dog_schema.id = str(uuid.uuid4())
    dog_schema.inherit_from = []

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.set(name=dog_schema.kind, schema=dog_schema)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.inherit_from.update",
        node_schema=dog_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestDog"),
        schema_branch=schema_branch,
    )

    checker = NodeInheritFromChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=dog_schema.id,
            kind="SchemaNode",
            field_name="inherit_from",
            value=["TestAnimal"],
        )
        in all_data_paths
    )


async def test_rename_generic_success(db: InfrahubDatabase, default_branch: Branch, animal_person_schema) -> None:
    branch = await create_branch(branch_name="branch", db=db)

    animal_schema = registry.schema.get(name="TestAnimal")
    dog_schema = registry.schema.get(name="TestDog")

    good_animal_schema = copy.deepcopy(animal_schema)
    good_animal_schema.name = "GoodAnimal"
    good_dog_schema = copy.deepcopy(dog_schema)
    good_dog_schema.inherit_from = [good_animal_schema.kind]

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.set(name=good_animal_schema.kind, schema=good_animal_schema)
    schema_branch.set(name=good_dog_schema.kind, schema=good_dog_schema)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.inherit_from.update",
        node_schema=good_dog_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=good_dog_schema.kind),
        schema_branch=schema_branch,
    )

    checker = NodeInheritFromChecker(db=db, branch=branch)

    grouped_data_paths = await checker.check(request=request)
    all_data_paths = list(chain(*[gdp.get_all_data_paths() for gdp in grouped_data_paths]))

    assert len(all_data_paths) == 0
