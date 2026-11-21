from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_attribute_renamed_while_a_new_attribute_takes_its_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_accord_main: Node,
) -> None:
    loaded_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    assert loaded_car.color.value == "#444444"

    current_schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=current_schema, branch=default_branch, db=db, at=Timestamp())
    previous_schema = registry.schema.get_schema_branch(name=default_branch.name)
    rollback_schema = previous_schema.duplicate()

    new_car_schema = previous_schema.get_node(name="TestCar", duplicate=False).duplicate()
    new_car_schema.get_attribute(name="color").name = "paint"
    new_car_schema.attributes.append(AttributeSchema(name="color", kind="Text", optional=True, default_value="red"))
    new_schema = previous_schema.duplicate()
    new_schema.set(name="TestCar", schema=new_car_schema)
    new_schema.process()

    diff = previous_schema.diff(other=new_schema)
    validation_result = previous_schema.validate_update(other=new_schema, diff=diff)
    assert sorted(migration.migration_name for migration in validation_result.migrations) == [
        "attribute.name.update",
        "node.attribute.add",
    ]

    coordinator = SchemaUpdateCoordinator(db=db, schema_manager=registry.schema, rollbacker=GraphRollbacker(db=db))
    await coordinator.execute(
        branch=default_branch,
        origin_schema=rollback_schema,
        rollback_schema=rollback_schema,
        candidate_schema=new_schema,
        at=Timestamp(),
        migration_executor=MigrationExecutor.DIRECT,
        diff=diff,
        migrations=validation_result.migrations,
        update_db=True,
        application_id=None,
    )

    # filters match stored attribute values only, while a loaded node falls back to the default of a missing attribute
    cars_by_paint = await NodeManager.query(db=db, schema="TestCar", filters={"paint__value": "#444444"})
    cars_by_color = await NodeManager.query(db=db, schema="TestCar", filters={"color__value": "red"})
    assert [car.id for car in cars_by_paint] == [car_accord_main.id]
    assert [car.id for car in cars_by_color] == [car_accord_main.id]
    await verify_graph(db=db, kinds=["TestCar"])
