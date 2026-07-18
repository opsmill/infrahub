"""Schema-level default values are applied and reverted on merge/rollback."""

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


@pytest.fixture
async def _base_car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    """Register the un-extended car/person schema (without the merge conftest's TestManufacturer)."""
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.mark.usefixtures("_base_car_person_schema")
async def test_diff_and_merge_schema_with_default_values(
    db: InfrahubDatabase,
    default_branch: Branch,
) -> None:
    schema_main = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(
        db=db, branch=default_branch, schema=schema_main, limit=["TestCar", "TestPerson"], update_db=True
    )
    branch2 = await create_branch(db=db, branch_name="branch2")
    schema_branch = registry.schema.get_schema_branch(name=branch2.name)
    schema_branch.duplicate()
    car_schema_branch = schema_branch.get(name="TestCar")
    car_schema_branch.attributes.append(AttributeSchema(name="num_cupholders", kind="Number", default_value=15))
    car_schema_branch.attributes.append(AttributeSchema(name="is_cool", kind="Boolean", default_value=False))
    car_schema_branch.attributes.append(AttributeSchema(name="nickname", kind="Text", default_value="car"))
    schema_branch.set(name="TestCar", schema=car_schema_branch)
    schema_branch.process()
    await registry.schema.update_schema_branch(
        db=db, branch=branch2, schema=schema_branch, limit=["TestCar", "TestPerson"], update_db=True
    )

    at = Timestamp()
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=at)

    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    car_schema_main = updated_schema.get(name="TestCar", duplicate=False)
    new_int_attr = car_schema_main.get_attribute(name="num_cupholders")
    assert new_int_attr.default_value == 15
    new_bool_attr = car_schema_main.get_attribute(name="is_cool")
    assert new_bool_attr.default_value is False
    new_str_attr = car_schema_main.get_attribute(name="nickname")
    assert new_str_attr.default_value == "car"

    await diff_merger.rollback(at=at)

    rolled_back_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    car_schema_main = rolled_back_schema.get(name="TestCar", duplicate=False)
    attribute_names = car_schema_main.attribute_names
    assert "num_cupholders" not in attribute_names
    assert "is_cool" not in attribute_names
    assert "nickname" not in attribute_names
    await verify_graph(db=db)
