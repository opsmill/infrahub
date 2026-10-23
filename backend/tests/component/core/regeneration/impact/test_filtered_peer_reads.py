from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import FieldLevelImpactResolver
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff, node_diff_element
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from .helpers import SUBSCRIBER_KIND, query_report

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def _cars_of_the_manufacturer(arguments: str) -> str:
    """A query where each car reads the cars of its manufacturer that the arguments select."""
    return (
        "query GetCarsOfTheManufacturer($ids: [ID!]!) {"
        " TestingCar(ids: $ids) { edges { node {"
        " name { value }"
        f" manufacturer {{ node {{ cars({arguments}) {{ edges {{ node {{ name {{ value }} }} }} }} }} }}"
        " } } } }"
    )


QUERY_RED_CARS_OF_THE_MANUFACTURER = _cars_of_the_manufacturer('color__value: "red"')


@dataclass(frozen=True, kw_only=True)
class AddedCarCase:
    name: str
    arguments: str
    added_color: str
    selects_every_target: bool


ADDED_CAR_CASES = [
    AddedCarCase(
        name="an_empty_filter_value_reads_every_car",
        arguments='color__value: ""',
        added_color="blue",
        selects_every_target=True,
    ),
    AddedCarCase(
        name="a_car_among_the_listed_values",
        arguments='color__values: ["red", "green"]',
        added_color="green",
        selects_every_target=True,
    ),
    AddedCarCase(
        name="a_car_outside_the_listed_values",
        arguments='color__values: ["red", "green"]',
        added_color="blue",
        selects_every_target=False,
    ),
    AddedCarCase(
        name="a_car_failing_one_of_two_filters",
        arguments='color__value: "red", name__value: "red-3"',
        added_color="red",
        selects_every_target=False,
    ),
    AddedCarCase(
        name="a_car_failing_an_attribute_property_filter",
        arguments="color__is_protected: true",
        added_color="red",
        selects_every_target=False,
    ),
]


@dataclass(frozen=True, kw_only=True)
class SecondReadCase:
    name: str
    query: str


# Each query reads the red cars of the manufacturer, and reads its cars a second time without a filter.
SECOND_READ_CASES = [
    SecondReadCase(
        name="in_an_inline_fragment_on_the_owner",
        query="""
query ($ids: [ID!]!) {
    TestingCar(ids: $ids) { edges { node {
        manufacturer { node {
            cars(color__value: "red") { edges { node { name { value } } } }
            ... on TestingManufacturer { cars { edges { node { name { value } } } } }
        } }
    } } }
}
""",
    ),
    SecondReadCase(
        name="in_a_named_fragment_on_the_owner",
        query="""
fragment AllCars on TestingManufacturer { cars { edges { node { name { value } } } } }

query ($ids: [ID!]!) {
    TestingCar(ids: $ids) { edges { node {
        manufacturer { node {
            cars(color__value: "red") { edges { node { name { value } } } }
            ...AllCars
        } }
    } } }
}
""",
    ),
    SecondReadCase(
        name="as_an_aliased_count",
        query="""
query ($ids: [ID!]!) {
    TestingCar(ids: $ids) { edges { node {
        manufacturer { node {
            cars(color__value: "red") { edges { node { name { value } } } }
            all_cars: cars { count }
        } }
    } } }
}
""",
    ),
]


class TestFilteredPeerReadImpact(TestInfrahubApp):
    """Select only the targets a filtered relationship read can see.

    One manufacturer makes every car, and three cars are targets. Each target is rendered through the query
    endpoint, so its group holds every node of its response: the two red cars and the manufacturer.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

        maker = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await maker.new(db=db, name="maker")
        await maker.save(db=db)
        owner = await Node.init(db=db, schema=TestKind.PERSON)
        await owner.new(db=db, name="owner")
        await owner.save(db=db)

        cars: dict[str, str] = {}
        for name, color in (("red-1", "red"), ("red-2", "red"), ("blue-1", "blue"), ("blue-2", "blue")):
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(db=db, name=name, color=color, owner=owner, manufacturer=maker)
            await car.save(db=db)
            cars[name] = car.id

        stored_query = await client.create(
            kind=InfrahubKind.GRAPHQLQUERY,
            name="GetRedCarsOfTheManufacturer",
            query=QUERY_RED_CARS_OF_THE_MANUFACTURER,
        )
        await stored_query.save()

        subscribers: dict[str, str] = {}
        for name in ("red-1", "red-2", "blue-1"):
            subscriber = await client.create(kind=SUBSCRIBER_KIND, name=f"{name}-artifact")
            await subscriber.save()
            await client.query_gql_query(
                name="GetRedCarsOfTheManufacturer",
                variables={"ids": [cars[name]]},
                update_group=True,
                subscribers=[subscriber.id],
            )
            subscribers[name] = subscriber.id

        return {"maker_id": maker.id, "owner_id": owner.id, "cars": cars, "subscribers": subscribers}

    async def _selected(
        self,
        *,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        diff_summary: list[NodeDiff],
        query: str = QUERY_RED_CARS_OF_THE_MANUFACTURER,
    ) -> set[str]:
        every_target = list(dataset["subscribers"].values())
        selection = await FieldLevelImpactResolver(db=db, client=client).resolve(
            query_report=query_report(query, default_branch),
            diff_summary=diff_summary,
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=every_target,
        )
        return set(selection.ids)

    @pytest.fixture
    async def add_car(
        self, db: InfrahubDatabase, dataset: dict[str, Any]
    ) -> AsyncGenerator[Callable[[str, str], Awaitable[str]], None]:
        """Add a car of the manufacturer for one test and delete it afterwards, so other tests see the same data."""
        added: list[Node] = []

        async def add(name: str, color: str) -> str:
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(db=db, name=name, color=color, owner=dataset["owner_id"], manufacturer=dataset["maker_id"])
            await car.save(db=db)
            added.append(car)
            return car.id

        yield add
        for car in added:
            await car.delete(db=db)

    def _car_added(self, *, dataset: dict[str, Any], car_id: str, branch: str) -> list[NodeDiff]:
        return [
            node_diff(
                node_id=car_id,
                kind=TestKind.CAR,
                branch=branch,
                action="ADDED",
                elements=[
                    node_diff_element(name="name", action="ADDED"),
                    node_diff_element(name="color", action="ADDED"),
                    node_diff_element(name="manufacturer", action="ADDED", element_type="RELATIONSHIP_ONE"),
                ],
            ),
            node_diff(
                node_id=dataset["maker_id"],
                kind=TestKind.MANUFACTURER,
                branch=branch,
                elements=[node_diff_element(name="cars", element_type="RELATIONSHIP_MANY")],
            ),
        ]

    async def test_adding_a_car_the_filter_excludes_selects_no_target(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        add_car: Callable[[str, str], Awaitable[str]],
    ) -> None:
        car_id = await add_car("blue-3", "blue")

        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=self._car_added(dataset=dataset, car_id=car_id, branch=default_branch.name),
        )

        assert selected == set()

    async def test_adding_a_car_the_filter_includes_selects_every_target(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        add_car: Callable[[str, str], Awaitable[str]],
    ) -> None:
        car_id = await add_car("red-3", "red")

        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=self._car_added(dataset=dataset, car_id=car_id, branch=default_branch.name),
        )

        assert selected == set(dataset["subscribers"].values())

    async def test_a_car_whose_color_changed_selects_every_target(
        self, db: InfrahubDatabase, dataset: dict[str, Any], default_branch: Branch, client: InfrahubClient
    ) -> None:
        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=[
                node_diff(
                    node_id=dataset["cars"]["blue-2"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["color"],
                )
            ],
        )

        assert selected == set(dataset["subscribers"].values())

    async def test_renaming_a_car_the_filter_excludes_selects_only_its_own_target(
        self, db: InfrahubDatabase, dataset: dict[str, Any], default_branch: Branch, client: InfrahubClient
    ) -> None:
        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=[
                node_diff(
                    node_id=dataset["cars"]["blue-1"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
        )

        assert selected == {dataset["subscribers"]["blue-1"]}

    @pytest.mark.parametrize("case", ADDED_CAR_CASES, ids=lambda case: case.name)
    async def test_adding_a_car_selects_every_target_only_when_the_filters_return_it(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        add_car: Callable[[str, str], Awaitable[str]],
        case: AddedCarCase,
    ) -> None:
        car_id = await add_car(f"{case.added_color}-new", case.added_color)

        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=self._car_added(dataset=dataset, car_id=car_id, branch=default_branch.name),
            query=_cars_of_the_manufacturer(case.arguments),
        )

        assert selected == (set(dataset["subscribers"].values()) if case.selects_every_target else set())

    async def test_adding_a_car_outside_the_ids_a_read_selects_selects_no_target(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        add_car: Callable[[str, str], Awaitable[str]],
    ) -> None:
        car_id = await add_car("red-3", "red")

        selected = await self._selected(
            db=db,
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=self._car_added(dataset=dataset, car_id=car_id, branch=default_branch.name),
            query=_cars_of_the_manufacturer(f'ids: ["{dataset["cars"]["red-1"]}"]'),
        )

        assert selected == set()

    @pytest.mark.parametrize("case", SECOND_READ_CASES, ids=lambda case: case.name)
    async def test_a_relationship_also_read_without_a_filter_selects_every_target(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        add_car: Callable[[str, str], Awaitable[str]],
        case: SecondReadCase,
    ) -> None:
        car_id = await add_car("blue-3", "blue")
        every_target = list(dataset["subscribers"].values())

        selection = await FieldLevelImpactResolver(db=db, client=client).resolve(
            query_report=query_report(case.query, default_branch),
            diff_summary=self._car_added(dataset=dataset, car_id=car_id, branch=default_branch.name),
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=every_target,
        )

        assert selection.widening is None
        assert set(selection.ids) == set(every_target)


class TestFilteredPeerReadImpactOnAComputedDiff(TestInfrahubApp):
    """Run the selection on a diff the application computes for a branch, rather than on a hand-built one.

    One manufacturer makes a red and a blue car, and both cars are targets. A branch adds a blue car.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

        maker = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await maker.new(db=db, name="maker")
        await maker.save(db=db)
        owner = await Node.init(db=db, schema=TestKind.PERSON)
        await owner.new(db=db, name="owner")
        await owner.save(db=db)
        cars: dict[str, str] = {}
        for name, color in (("red-1", "red"), ("blue-1", "blue")):
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(db=db, name=name, color=color, owner=owner, manufacturer=maker)
            await car.save(db=db)
            cars[name] = car.id

        stored_query = await client.create(
            kind=InfrahubKind.GRAPHQLQUERY, name="GetRedCarsOfTheManufacturer", query=QUERY_RED_CARS_OF_THE_MANUFACTURER
        )
        await stored_query.save()
        subscribers: dict[str, str] = {}
        for name, car_id in cars.items():
            subscriber = await client.create(kind=SUBSCRIBER_KIND, name=f"{name}-artifact")
            await subscriber.save()
            await client.query_gql_query(
                name="GetRedCarsOfTheManufacturer",
                variables={"ids": [car_id]},
                update_group=True,
                subscribers=[subscriber.id],
            )
            subscribers[name] = subscriber.id

        branch = await client.branch.create(branch_name="add-a-blue-car", sync_with_git=False)
        added = await client.create(
            kind=TestKind.CAR, branch=branch.name, name="blue-2", color="blue", owner=owner.id, manufacturer=maker.id
        )
        await added.save()
        await client.create_diff(
            branch=branch.name,
            name="add-a-blue-car",
            from_time=datetime.fromisoformat(branch.branched_from),
            to_time=datetime.now(tz=UTC),
        )
        diff_summary = await client.get_diff_summary(branch=branch.name, name="add-a-blue-car")

        return {
            "maker_id": maker.id,
            "added_car_id": added.id,
            "subscribers": subscribers,
            "branch": await registry.get_branch(db=db, branch=branch.name),
            "diff_summary": diff_summary,
        }

    async def _selected(
        self, *, db: InfrahubDatabase, dataset: dict[str, Any], client: InfrahubClient, query: str
    ) -> set[str]:
        every_target = list(dataset["subscribers"].values())
        selection = await FieldLevelImpactResolver(db=db, client=client).resolve(
            query_report=query_report(query, dataset["branch"]),
            diff_summary=dataset["diff_summary"],
            query_branch=dataset["branch"].name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=every_target,
        )
        return set(selection.ids)

    async def test_the_diff_records_the_change_on_the_car_and_on_the_manufacturer(
        self, dataset: dict[str, Any]
    ) -> None:
        entries = {entry["id"]: entry for entry in dataset["diff_summary"]}

        assert entries[dataset["added_car_id"]]["action"] == "ADDED"
        assert "manufacturer" in {element["name"] for element in entries[dataset["added_car_id"]]["elements"]}
        assert entries[dataset["maker_id"]]["action"] == "UPDATED"
        assert {element["name"] for element in entries[dataset["maker_id"]]["elements"]} == {"cars"}

    async def test_adding_a_car_the_filter_excludes_selects_no_target(
        self, db: InfrahubDatabase, dataset: dict[str, Any], client: InfrahubClient
    ) -> None:
        assert (
            await self._selected(db=db, dataset=dataset, client=client, query=QUERY_RED_CARS_OF_THE_MANUFACTURER)
            == set()
        )

    async def test_adding_a_car_selects_every_target_of_a_read_without_filter(
        self, db: InfrahubDatabase, dataset: dict[str, Any], client: InfrahubClient
    ) -> None:
        selected = await self._selected(
            db=db, dataset=dataset, client=client, query=_cars_of_the_manufacturer("limit: 50")
        )

        assert selected == set(dataset["subscribers"].values())


# A maker's vehicles are of two kinds: a sedan declares its side of the relationship, a lorry does not, so the
# diff records a lorry joining a maker only on the maker.
VEHICLE_KIND = "TestingMotorVehicle"
SEDAN_KIND = "TestingSedan"
LORRY_KIND = "TestingLorry"
MAKER_KIND = "TestingVehicleMaker"
MAKER_VEHICLES = "maker__vehicles"
MIXED_VEHICLE_SCHEMA = SchemaRoot(
    generics=[
        GenericSchema(
            name="MotorVehicle",
            namespace="Testing",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text"),
            ],
        )
    ],
    nodes=[
        NodeSchema(
            name="VehicleMaker",
            namespace="Testing",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="vehicles",
                    peer=VEHICLE_KIND,
                    cardinality=RelationshipCardinality.MANY,
                    identifier=MAKER_VEHICLES,
                    optional=True,
                )
            ],
        ),
        NodeSchema(
            name="Sedan",
            namespace="Testing",
            inherit_from=[VEHICLE_KIND],
            relationships=[
                RelationshipSchema(
                    name="maker",
                    peer=MAKER_KIND,
                    cardinality=RelationshipCardinality.ONE,
                    identifier=MAKER_VEHICLES,
                    optional=True,
                )
            ],
        ),
        NodeSchema(name="Lorry", namespace="Testing", inherit_from=[VEHICLE_KIND]),
    ],
)

QUERY_RED_VEHICLES_OF_THE_MAKER = (
    "query GetRedVehiclesOfTheMaker($ids: [ID!]!) {"
    f" {MAKER_KIND}(ids: $ids) {{ edges {{ node {{"
    ' name { value } vehicles(color__value: "red") { edges { node { name { value } } } }'
    " } } } }"
)


class TestFilteredPeerReadImpactOnPeersMissingFromTheDiff(TestInfrahubApp):
    """Select the targets of each maker whose vehicles changed, when some vehicles do not record the change.

    Two makers are targets. A branch adds a red lorry to the first maker, which the diff records only on the maker,
    and adds a blue sedan to the second maker.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)
        await load_schema(db=db, schema=MIXED_VEHICLE_SCHEMA, update_db=True)

        makers: dict[str, str] = {}
        for name in ("maker-1", "maker-2"):
            maker = await Node.init(db=db, schema=MAKER_KIND)
            await maker.new(db=db, name=name)
            await maker.save(db=db)
            makers[name] = maker.id
        lorry = await Node.init(db=db, schema=LORRY_KIND)
        await lorry.new(db=db, name="red-lorry", color="red")
        await lorry.save(db=db)
        sedan = await Node.init(db=db, schema=SEDAN_KIND)
        await sedan.new(db=db, name="blue-sedan", color="blue")
        await sedan.save(db=db)

        stored_query = await client.create(
            kind=InfrahubKind.GRAPHQLQUERY, name="GetRedVehiclesOfTheMaker", query=QUERY_RED_VEHICLES_OF_THE_MAKER
        )
        await stored_query.save()
        subscribers: dict[str, str] = {}
        for name, maker_id in makers.items():
            subscriber = await client.create(kind=SUBSCRIBER_KIND, name=f"{name}-artifact")
            await subscriber.save()
            await client.query_gql_query(
                name="GetRedVehiclesOfTheMaker",
                variables={"ids": [maker_id]},
                update_group=True,
                subscribers=[subscriber.id],
            )
            subscribers[name] = subscriber.id

        branch = await client.branch.create(branch_name="add-vehicles-to-makers", sync_with_git=False)
        first_maker = await client.get(kind=MAKER_KIND, id=makers["maker-1"], branch=branch.name)
        await first_maker.vehicles.fetch()
        first_maker.vehicles.add(lorry.id)
        await first_maker.save()
        branch_sedan = await client.get(kind=SEDAN_KIND, id=sedan.id, branch=branch.name)
        branch_sedan.maker = makers["maker-2"]
        await branch_sedan.save()
        await client.create_diff(
            branch=branch.name,
            name="add-vehicles-to-makers",
            from_time=datetime.fromisoformat(branch.branched_from),
            to_time=datetime.now(tz=UTC),
        )
        diff_summary = await client.get_diff_summary(branch=branch.name, name="add-vehicles-to-makers")

        return {
            "makers": makers,
            "lorry_id": lorry.id,
            "subscribers": subscribers,
            "branch": await registry.get_branch(db=db, branch=branch.name),
            "diff_summary": diff_summary,
        }

    async def test_the_diff_records_the_lorry_joining_its_maker_only_on_the_maker(
        self, dataset: dict[str, Any]
    ) -> None:
        entries = {entry["id"]: entry for entry in dataset["diff_summary"]}

        assert dataset["lorry_id"] not in entries
        assert {element["name"] for element in entries[dataset["makers"]["maker-1"]]["elements"]} == {"vehicles"}

    async def test_adding_a_vehicle_the_filter_includes_selects_its_maker_target(
        self, db: InfrahubDatabase, dataset: dict[str, Any], client: InfrahubClient
    ) -> None:
        selection = await FieldLevelImpactResolver(db=db, client=client).resolve(
            query_report=query_report(QUERY_RED_VEHICLES_OF_THE_MAKER, dataset["branch"]),
            diff_summary=dataset["diff_summary"],
            query_branch=dataset["branch"].name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=list(dataset["subscribers"].values()),
        )

        assert dataset["subscribers"]["maker-1"] in set(selection.ids)
