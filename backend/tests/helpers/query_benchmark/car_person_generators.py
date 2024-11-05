import random
import uuid
from typing import Any, Optional, Tuple

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.helpers.query_benchmark.data_generator import DataGenerator
from tests.helpers.query_benchmark.db_query_profiler import InfrahubDatabaseProfiler


class CarGenerator(DataGenerator):
    async def load_data(self, nb_elements: int) -> None:
        default_branch = await registry.get_branch(db=self.db)
        await self.load_cars(default_branch, nb_elements)

    async def load_car_random_name(self, branch: Branch, nbr_seats: int, **kwargs: Any) -> Node:
        car_schema = registry.schema.get_node_schema(name="TestCar", branch=branch)

        short_id = str(uuid.uuid4())[:8]
        car_name = f"car-{short_id}"
        car_node = await Node.init(db=self.db, schema=car_schema, branch=branch)
        await car_node.new(db=self.db, name=car_name, nbr_seats=nbr_seats, **kwargs)

        return await car_node.save(db=self.db)

    async def load_cars(self, branch: Branch, nb_cars: int, **kwargs: Any) -> dict[str, Node]:
        cars = {}
        for _ in range(nb_cars):
            car_node = await self.load_car_random_name(nbr_seats=4, branch=branch, **kwargs)
            cars[car_node.name.value] = car_node  # type: ignore[attr-defined]

        return cars


class EngineGenerator(DataGenerator):
    async def load_data(self, nb_elements: int) -> None:
        default_branch = await registry.get_branch(db=self.db)
        await self.load_engines(default_branch, nb_elements)

    async def load_engines(self, branch: Branch, nb_cars: int, **kwargs: Any) -> dict[str, Node]:
        engines = {}
        for _ in range(nb_cars):
            engine_node = await self.load_engine_random_name(branch=branch, **kwargs)
            engines[engine_node.name.value] = engine_node  # type: ignore[attr-defined]

        return engines

    async def load_engine_random_name(self, branch: Branch, **kwargs: Any) -> Node:
        engine_schema = registry.schema.get_node_schema(name="TestEngine", branch=branch)

        short_id = str(uuid.uuid4())[:8]
        engine_name = f"engine-{short_id}"
        engine_node = await Node.init(db=self.db, schema=engine_schema, branch=branch)
        await engine_node.new(db=self.db, name=engine_name, **kwargs)

        return await engine_node.save(db=self.db)


class CarWithDiffInSecondBranchGenerator(CarGenerator):
    persons: Optional[dict[str, Node]]  # mapping of existing cars names -> node
    nb_persons: int
    diff_ratio: float  # 0.1 means 10% of added nodes, 10% of deleted nodes, 10% of modified nodes
    main_branch: Branch
    diff_branch: Branch

    def __init__(
        self, db: InfrahubDatabaseProfiler, nb_persons: int, diff_ratio: float, main_branch: Branch, diff_branch: Branch
    ) -> None:
        super().__init__(db)
        self.persons = None
        self.nb_persons = nb_persons
        self.diff_ratio = diff_ratio
        self.main_branch = main_branch
        self.diff_branch = diff_branch

    async def init(self) -> None:
        """Load persons, that will be later connected to generated cars."""
        self.persons = await PersonGenerator(self.db).load_persons(nb_persons=self.nb_persons)

    async def load_cars_with_multiple_rels(self, branch: Branch, nb_cars: int) -> dict[str, Node]:
        assert self.persons is not None
        engine_generator = EngineGenerator(db=self.db)

        cars = {}
        for _ in range(nb_cars):
            owner = random.choice([self.persons[person_name] for person_name in self.persons])
            drivers = random.choices([self.persons[person_name] for person_name in self.persons], k=nb_cars)
            engine = await engine_generator.load_engine_random_name(branch=branch)
            car = await self.load_car_random_name(
                branch=branch, nbr_seats=4, owner=owner, drivers=drivers, engine=engine
            )
            cars[car.name.value] = car  # type: ignore[attr-defined]

        return cars

    async def load_data(self, nb_elements: int) -> None:
        """
        Load cars in main branch, rebase diff branch on main branch, then load changes
        within diff branch according to a given ratio.
        Differences are:
        - Updates some cars attributes as well as 1:1, 1:N, N:N relationships.
        - Add new cars.
        Note that we do not delete cars within diff branch as it seems to take too long.
        """

        assert self.persons is not None, "'init' method should be called before 'load_data'"

        if nb_elements == 0:
            return

        # Load cars in main branch
        new_cars = await self.load_cars_with_multiple_rels(nb_cars=nb_elements, branch=self.main_branch)

        # Integrate these new cars in diff branch
        await self.diff_branch.rebase(self.db)

        # Retrieve car nodes from diff branch, including the ones not present in main branch
        # that were created by prior calls to `load_data`
        car_schema = registry.schema.get_node_schema(name="TestCar", branch=self.diff_branch)
        car_nodes = await NodeManager.query(db=self.db, schema=car_schema, branch=self.diff_branch)
        new_car_nodes = [car_node for car_node in car_nodes if car_node.name.value in new_cars]

        nb_diff = max(int(nb_elements * self.diff_ratio), 1)

        # Update cars in diff branch
        car_nodes_updatable = new_car_nodes
        car_nodes_to_update = random.choices(car_nodes_updatable, k=nb_diff)
        for i, car_node in enumerate(car_nodes_to_update):
            car_node.name.value = f"updated-car-{str(uuid.uuid4())[:8]}"

            # Permute engines among car nodes to update, so it keeps one-to-one relationship between cars-engines
            new_engine = car_nodes_to_update[(i + 1) % len(car_nodes_to_update)].engine
            car_node.engine.update(db=self.db, data=new_engine)

            # Update one-to-many relationship
            new_owner = random.choice([self.persons[person_name] for person_name in self.persons])
            car_node.owner.update(db=self.db, data=new_owner)

            # Update many-to-many relationship
            new_drivers = random.choices([self.persons[person_name] for person_name in self.persons])
            car_node.drivers.update(db=self.db, data=new_drivers)

            await car_node.save(db=self.db)

        # Add a few cars in diff branch
        added_cars = await self.load_cars_with_multiple_rels(nb_cars=nb_diff, branch=self.diff_branch)

        assert len(added_cars) == len(car_nodes_to_update) == nb_diff


class PersonGenerator(DataGenerator):
    async def load_data(self, nb_elements: int) -> None:
        await self.load_persons(nb_persons=nb_elements)

    async def load_persons(
        self,
        nb_persons: int,
        cars: Optional[dict[str, Node]] = None,
    ) -> dict[str, Node]:
        """
        Load persons and return a mapping person_name -> person_node.
        If 'cars' is specified, each person created is linked to a few random cars.
        """

        default_branch = await registry.get_branch(db=self.db)
        person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)

        persons_names_to_nodes = {}
        for _ in range(nb_persons):
            short_id = str(uuid.uuid4())[:8]
            person_name = f"person-{short_id}"
            person_node = await Node.init(db=self.db, schema=person_schema, branch=default_branch)

            if cars is not None:
                random_cars = [cars[car_name] for car_name in random.choices(list(cars.keys()), k=5)]
                await person_node.new(db=self.db, name=person_name, cars=random_cars)
            else:
                await person_node.new(db=self.db, name=person_name)

            async with self.db.start_session():
                await person_node.save(db=self.db)

            persons_names_to_nodes[person_name] = person_node

        return persons_names_to_nodes


class CarGeneratorWithOwnerHavingUniqueCar(CarGenerator):
    persons: list[Tuple[str, Node]]  # mapping of existing cars names -> node
    nb_persons: int
    nb_cars_loaded: int

    def __init__(self, db: InfrahubDatabaseProfiler, nb_persons: int) -> None:
        super().__init__(db)
        self.nb_persons = nb_persons
        self.persons = []
        self.nb_cars_loaded = 0

    async def init(self) -> None:
        """Load persons, that will be later connected to generated cars."""
        persons = await PersonGenerator(self.db).load_persons(nb_persons=self.nb_persons)
        self.persons = list(persons.items())

    async def load_data(self, nb_elements: int) -> None:
        """
        Generate cars with an owner, in a way that an owner can't have multiple cars.
        Also generate distinct nb_seats per car.
        """

        default_branch = await registry.get_branch(db=self.db)
        car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)

        for i in range(nb_elements):
            short_id = str(uuid.uuid4())[:8]
            car_name = f"car-{short_id}"
            car_node = await Node.init(db=self.db, schema=car_schema, branch=default_branch)

            await car_node.new(
                db=self.db,
                name=car_name,
                nbr_seats=self.nb_cars_loaded + i,
                owner=self.persons[self.nb_cars_loaded + i][1],
            )

            async with self.db.start_session():
                await car_node.save(db=self.db)

        self.nb_cars_loaded += nb_elements
