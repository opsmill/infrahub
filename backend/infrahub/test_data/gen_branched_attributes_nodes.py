import random
import uuid

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.log import get_logger

from .shared import DataGenerator

log = get_logger()


class GenerateBranchedAttributeNodes(DataGenerator):
    async def load_data(
        self,
        nbr_cars: int = 100,
    ) -> None:
        """Generate a large number of Cars with attribute values on a branch called 'branch'"""
        default_branch = await registry.get_branch(db=self.db)

        if self.progress:
            task_car = self.progress.add_task("Creating Cars...", total=nbr_cars)

        cars = []

        car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)
        batch = self.create_batch()
        for _ in range(nbr_cars):
            name = str(uuid.uuid4())[:16]
            nbr_seats = random.randint(1, 100)
            color = "#" + str(uuid.uuid4())[:6]
            is_electric = True
            obj = await Node.init(db=self.db, schema=car_schema, branch=default_branch)
            await obj.new(db=self.db, name=name, nbr_seats=nbr_seats, color=color, is_electric=is_electric)
            batch.add(task=self.save_obj, obj=obj)
            cars.append(obj)

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_car)

        if self.progress:
            task_update_car = self.progress.add_task("Updating Cars...", total=nbr_cars)

        branch = await create_branch(db=self.db, branch_name="branch")
        batch = self.create_batch()
        for car in cars:
            branch_car = await NodeManager.get_one(db=self.db, branch=branch, id=car.id)
            car.name.value = str(uuid.uuid4())[:16]  # type: ignore[attr-defined]
            car.nbr_seats.value = random.randint(1, 100)  # type: ignore[attr-defined]
            car.color.value = "#" + str(uuid.uuid4())[:6]  # type: ignore[attr-defined]
            car.is_electric.value = False  # type: ignore[attr-defined]
            batch.add(task=self.save_obj, obj=branch_car)

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_update_car)
