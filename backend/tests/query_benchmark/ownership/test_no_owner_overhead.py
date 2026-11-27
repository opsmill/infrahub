from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.protocols import CoreGeneratorDefinition
from infrahub_sdk.spec.object import ObjectFile

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.query_benchmark.ownership.conftest import (
    DEVICE_KIND,
    INTERFACE_KIND,
    LOCATION_LEVELS,
    NB_ACCOUNT_GROUPS,
    NB_INTERFACES_PER_DEVICE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.query_benchmark.ownership.conftest import ReferenceDataSet

PAGE_SIZE = 50
NB_OBJECT_FILE_DEVICES = 10
NB_OBJECT_FILE_INTERFACES = 4

DEVICE_PAGE = """
query ($limit: Int) {
    BenchDevice(limit: $limit) {
        count
        edges { node { id name { value } role { value } rack { node { id } } } }
    }
}
"""

INTERFACE_PAGE = """
query ($limit: Int) {
    BenchInterface(limit: $limit) {
        count
        edges { node { id name { value } enabled { value } device { node { id } } } }
    }
}
"""

INTERFACES_OF_DEVICE = """
query ($device: [ID], $limit: Int) {
    BenchInterface(device__ids: $device, limit: $limit) {
        count
        edges { node { id name { value } enabled { value } } }
    }
}
"""

DEVICE_BY_NAME = """
query ($name: String, $limit: Int) {
    BenchDevice(name__value: $name, limit: $limit) {
        count
        edges { node { id name { value } } }
    }
}
"""

INTERFACE_CREATE = """
mutation ($name: String!, $device: String!) {
    BenchInterfaceCreate(data: { name: { value: $name }, device: { id: $device } }) { ok object { id } }
}
"""

INTERFACE_UPDATE = """
mutation ($id: String!, $description: String!) {
    BenchInterfaceUpdate(data: { id: $id, description: { value: $description } }) { ok }
}
"""

INTERFACE_DELETE = """
mutation ($id: String!) {
    BenchInterfaceDelete(data: { id: $id }) { ok }
}
"""

DEVICE_DELETE = """
mutation ($id: String!) {
    BenchDeviceDelete(data: { id: $id }) { ok }
}
"""


async def _median_ms(call: Callable[[int], Awaitable[None]], nb_runs: int) -> float:
    durations: list[float] = []
    for run in range(nb_runs):
        start = time.perf_counter()
        await call(run)
        durations.append(time.perf_counter() - start)
    return statistics.median(durations) * 1000


def _report(data_set: ReferenceDataSet, rows: dict[str, float], nb_runs: int) -> None:
    print(
        f"\n{len(data_set.device_ids)} devices, {data_set.nb_interfaces} interfaces,"
        f" {sum(len(ids) for ids in data_set.location_ids.values())} locations in {len(LOCATION_LEVELS)} levels,"
        f" {NB_ACCOUNT_GROUPS} account groups, median of {nb_runs} runs"
    )
    for label, median_ms in rows.items():
        print(f"| {label:<55} | {median_ms:>9.1f} ms |")


@pytest.fixture(scope="class")
async def generator_definition_id(
    db: InfrahubDatabase,
    reference_data_set: ReferenceDataSet,
    client: InfrahubClient,
    git_repos_dir_module_scope: Path,
    git_repos_source_dir_module_scope: Path,
) -> str:
    """Import a repository with a generator that creates one tag for each car of each person of a group."""
    await load_schema(db=db, schema=CAR_SCHEMA)
    person = await Node.init(db=db, schema=TestKind.PERSON)
    await person.new(db=db, name="John", height=175)
    await person.save(db=db)
    manufacturer = await Node.init(db=db, schema=TestKind.MANUFACTURER)
    await manufacturer.new(db=db, name="Koenigsegg")
    await manufacturer.save(db=db)
    car = await Node.init(db=db, schema=TestKind.CAR)
    await car.new(db=db, name="Jesko", color="Red", owner=person, manufacturer=manufacturer)
    await car.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="people", members=[person])
    await group.save(db=db)

    FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
    repository = await client.create(
        kind=InfrahubKind.REPOSITORY,
        data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
    )
    await repository.save()
    definition = await client.get(kind=CoreGeneratorDefinition, name__value="cartags")
    return definition.id


@pytest.mark.timeout(36000)
class TestNoOwnerOverhead(TestInfrahubApp):
    """Print the time of the operations of a customer who does not use owners, on the reference data set.

    The tests check the counts and the results, so a number never comes from an operation that failed.
    """

    nb_runs = 20
    nb_long_runs = 5
    """An object file load and a generator run are many requests each, so they get fewer runs."""

    async def test_list_queries(self, reference_data_set: ReferenceDataSet, client: InfrahubClient) -> None:
        nb_devices = len(reference_data_set.device_ids)
        queries: dict[str, tuple[str, dict[str, str | list[str]], str, int]] = {
            "List: first page of devices": (DEVICE_PAGE, {}, DEVICE_KIND, nb_devices),
            "List: first page of interfaces": (INTERFACE_PAGE, {}, INTERFACE_KIND, reference_data_set.nb_interfaces),
            "List: interfaces of one device": (
                INTERFACES_OF_DEVICE,
                {"device": [reference_data_set.device_ids[0]]},
                INTERFACE_KIND,
                NB_INTERFACES_PER_DEVICE,
            ),
            "List: one device by name": (DEVICE_BY_NAME, {"name": "device-00000"}, DEVICE_KIND, 1),
        }

        rows: dict[str, float] = {}
        for label, (query, filters, kind, expected_count) in queries.items():
            variables = {"limit": PAGE_SIZE, **filters}
            # The first call warms the caches of the database and of the GraphQL schema, so it is left out.
            response = await client.execute_graphql(query=query, variables=variables)
            assert response[kind]["count"] == expected_count

            async def call(run: int, query: str = query, variables: dict[str, Any] = variables) -> None:
                await client.execute_graphql(query=query, variables=variables)

            rows[label] = await _median_ms(call, nb_runs=self.nb_runs)

        _report(data_set=reference_data_set, rows=rows, nb_runs=self.nb_runs)

    async def test_create_update_delete(self, reference_data_set: ReferenceDataSet, client: InfrahubClient) -> None:
        device_id = reference_data_set.device_ids[0]
        interface_ids: list[str] = []

        async def create(run: int) -> None:
            response = await client.execute_graphql(
                query=INTERFACE_CREATE, variables={"name": f"bench-{run}", "device": device_id}
            )
            interface_ids.append(response[f"{INTERFACE_KIND}Create"]["object"]["id"])

        async def update(run: int) -> None:
            response = await client.execute_graphql(
                query=INTERFACE_UPDATE, variables={"id": interface_ids[run], "description": f"run {run}"}
            )
            assert response[f"{INTERFACE_KIND}Update"]["ok"]

        async def delete(run: int) -> None:
            response = await client.execute_graphql(query=INTERFACE_DELETE, variables={"id": interface_ids[run]})
            assert response[f"{INTERFACE_KIND}Delete"]["ok"]

        rows = {
            "Mutation: create one interface": await _median_ms(create, nb_runs=self.nb_runs),
            "Mutation: update one interface": await _median_ms(update, nb_runs=self.nb_runs),
            "Mutation: delete one interface": await _median_ms(delete, nb_runs=self.nb_runs),
        }

        response = await client.execute_graphql(
            query=INTERFACES_OF_DEVICE, variables={"device": [device_id], "limit": PAGE_SIZE}
        )
        assert response[INTERFACE_KIND]["count"] == NB_INTERFACES_PER_DEVICE
        _report(data_set=reference_data_set, rows=rows, nb_runs=self.nb_runs)

    async def test_object_file_load(self, reference_data_set: ReferenceDataSet, client: InfrahubClient) -> None:
        def device_names(run: int) -> list[str]:
            return [f"object-file-{run}-{index}" for index in range(NB_OBJECT_FILE_DEVICES)]

        async def load(run: int) -> None:
            object_file = ObjectFile(
                location=Path("devices.yml"),
                content={
                    "apiVersion": "infrahub.app/v1",
                    "kind": "Object",
                    "spec": {
                        "kind": DEVICE_KIND,
                        "data": [
                            {
                                "name": name,
                                "role": "leaf",
                                "rack": "rack-0-0",
                                "interfaces": {
                                    "data": [{"name": f"eth{number}"} for number in range(NB_OBJECT_FILE_INTERFACES)]
                                },
                            }
                            for name in device_names(run)
                        ],
                    },
                },
            )
            object_file.validate_content()
            await object_file.process(client=client)

        names = [name for run in range(self.nb_long_runs) for name in device_names(run)]
        rows = {
            f"Object file: {NB_OBJECT_FILE_DEVICES} devices with {NB_OBJECT_FILE_INTERFACES} interfaces each": (
                await _median_ms(load, nb_runs=self.nb_long_runs)
            )
        }

        devices = await client.filters(kind=DEVICE_KIND, name__values=names)
        assert len(devices) == len(names)
        response = await client.execute_graphql(
            query=INTERFACES_OF_DEVICE, variables={"device": [device.id for device in devices], "limit": PAGE_SIZE}
        )
        assert response[INTERFACE_KIND]["count"] == len(names) * NB_OBJECT_FILE_INTERFACES

        async def delete_device(run: int) -> None:
            response = await client.execute_graphql(query=DEVICE_DELETE, variables={"id": devices[run].id})
            assert response[f"{DEVICE_KIND}Delete"]["ok"]

        # The delete of a device also deletes its interfaces.
        rows[f"Mutation: delete one device with {NB_OBJECT_FILE_INTERFACES} interfaces"] = await _median_ms(
            delete_device, nb_runs=self.nb_long_runs
        )
        response = await client.execute_graphql(
            query=INTERFACES_OF_DEVICE, variables={"device": [device.id for device in devices], "limit": PAGE_SIZE}
        )
        assert response[INTERFACE_KIND]["count"] == (len(names) - self.nb_long_runs) * NB_OBJECT_FILE_INTERFACES
        _report(data_set=reference_data_set, rows=rows, nb_runs=self.nb_long_runs)

    async def test_generator_run(
        self, reference_data_set: ReferenceDataSet, generator_definition_id: str, client: InfrahubClient
    ) -> None:
        mutation = Mutation(
            mutation="CoreGeneratorDefinitionRun",
            input_data={"data": {"id": generator_definition_id}},
            query={"ok": None},
        ).render()

        async def run_generator(run: int) -> None:
            response = await client.execute_graphql(query=mutation)
            assert response["CoreGeneratorDefinitionRun"]["ok"]

        rows = {"Generator: one run, one target, one tag": await _median_ms(run_generator, nb_runs=self.nb_long_runs)}

        tags = await client.all(kind=TestKind.TAG)
        assert "john-jesko" in [tag.name.value for tag in tags]
        _report(data_set=reference_data_set, rows=rows, nb_runs=self.nb_long_runs)
