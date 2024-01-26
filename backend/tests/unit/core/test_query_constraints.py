from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.constraints import NodeConstraintsUniquenessQuery
from infrahub.database import InfrahubDatabase


async def test_query_uniqueness(
    db: InfrahubDatabase,
    car_accord_main,
    car_camry_main: Node,
    car_volt_main,
    car_yaris_main,
    car_yaris2_main,
    car_prius_main,
    branch: Branch,
):
    node_to_delete = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)

    car_volt = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    car_volt.nbr_seats.value = 3
    await car_volt.save(db=db)

    car_volt = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    car_volt.nbr_seats.value = 2
    await car_volt.save(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)

    breakpoint()

    query = await NodeConstraintsUniquenessQuery.init(
        db=db, branch=branch, schema=schema, constraints={"is_electric__value": False}
    )
    await query.execute(db=db)
