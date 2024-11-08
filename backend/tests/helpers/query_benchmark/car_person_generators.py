import random
import uuid
from typing import Optional, Tuple

from infrahub.core import registry
from infrahub.core.node import Node
from tests.helpers.query_benchmark.data_generator import DataGenerator
from tests.helpers.query_benchmark.db_query_profiler import InfrahubDatabaseProfiler


class CarGenerator(DataGenerator):
    async def load_data(self, nb_elements: int) -> None:
        await self.load_cars(nb_elements)

    async def load_cars(self, nb_cars: int, persons: Optional[dict[str, Node]] = None) -> dict[str, Node]:
        """
        Load cars and return a mapping car_name -> car_node.
        If 'persons' is specified, each car created is linked to a person.
        """

        default_branch = await registry.get_branch(db=self.db)
        car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)

        cars = {}
        for _ in range(nb_cars):
            short_id = str(uuid.uuid4())[:8]
            car_name = f"car-{short_id}"
            car_node = await Node.init(db=self.db, schema=car_schema, branch=default_branch)
            if persons is not None:
                random_person = random.choice([persons[person_name] for person_name in persons])
                await car_node.new(db=self.db, name=car_name, nbr_seats=4, owner=random_person)
            else:
                await car_node.new(db=self.db, name=car_name, nbr_seats=4)

            async with self.db.start_session():
                await car_node.save(db=self.db)

            cars[car_name] = car_node

        return cars


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


class PersonFromExistingCarGenerator(PersonGenerator):
    cars: Optional[dict[str, Node]]  # mapping of existing cars names -> node
    nb_cars: int

    def __init__(self, db: InfrahubDatabaseProfiler, nb_cars: int) -> None:
        super().__init__(db)
        self.nb_cars = nb_cars
        self.cars = None

    async def init(self) -> None:
        """Load cars, that will be later connected to generated persons."""
        self.cars = await CarGenerator(self.db).load_cars(nb_cars=self.nb_cars)

    async def load_data(self, nb_elements: int) -> None:
        assert self.cars is not None, "'init' method should be called before 'load_data'"
        await self.load_persons(nb_persons=nb_elements, cars=self.cars)


class CarFromExistingPersonGenerator(CarGenerator):
    persons: Optional[dict[str, Node]]  # mapping of existing cars names -> node
    nb_persons: int

    def __init__(self, db: InfrahubDatabaseProfiler, nb_persons: int) -> None:
        super().__init__(db)
        self.nb_persons = nb_persons
        self.persons = None

    async def init(self) -> None:
        """Load persons, that will be later connected to generated cars."""
        self.persons = await PersonGenerator(self.db).load_persons(nb_persons=self.nb_persons)

    async def load_data(self, nb_elements: int) -> None:
        assert self.persons is not None, "'init' method should be called before 'load_data'"
        await self.load_cars(nb_cars=nb_elements, persons=self.persons)


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


class CarAndPersonIsolatedGenerator(DataGenerator):
    def __init__(self, db: InfrahubDatabaseProfiler) -> None:
        super().__init__(db)
        self.car_generator: CarGenerator = CarGenerator(db)
        self.person_generator: PersonGenerator = PersonGenerator(db)

    async def load_data(self, nb_elements: int) -> None:
        """
        Load not connected cars and persons. Note that 'nb_elements' cars plus 'nb_elements' persons are loaded.
        """

        await self.car_generator.load_cars(nb_cars=nb_elements)
        await self.person_generator.load_persons(nb_persons=nb_elements)


class CarAndPersonConnectedGenerator(DataGenerator):
    def __init__(self, db: InfrahubDatabaseProfiler) -> None:
        super().__init__(db)
        self.car_generator: CarGenerator = CarGenerator(db)
        self.person_generator: PersonGenerator = PersonGenerator(db)

    async def load_data(self, nb_elements: int) -> None:
        """
        Load connected cars and persons. Note that 'nb_elements' cars plus 'nb_elements' persons are loaded.
        """

        persons = await self.person_generator.load_persons(nb_persons=nb_elements)
        await self.car_generator.load_cars(nb_cars=nb_elements, persons=persons)
