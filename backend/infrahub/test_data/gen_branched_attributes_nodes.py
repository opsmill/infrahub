import random
import uuid

from infrahub.core import registry
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
            task_update_car = self.progress.add_task("Updating Cars...", total=nbr_cars)

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

        batch = self.create_batch()
        for car in cars:
            batch.add(task=self._random_car_update, branch=None, car_id=car.id)

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_update_car)

    async def _random_car_update(self, car_id, branch=None) -> None:
        random_seed = random.randint(0, 10)
        do_delete = random_seed in (5, 7)
        while random_seed > 0:
            car = await NodeManager.get_one(db=self.db, branch=branch, id=car_id)
            car.name.value = str(uuid.uuid4())[:16]  # type: ignore[attr-defined]
            car.nbr_seats.value = random.randint(1, 10)  # type: ignore[attr-defined]
            car.color.value = "#" + str(uuid.uuid4())[:6]  # type: ignore[attr-defined]
            car.is_electric.value = not bool(car.is_electric.value)  # type: ignore[attr-defined]
            random_seed -= 2
            await self.save_obj(obj=car)
        if do_delete:
            await car.delete(db=self.db)
