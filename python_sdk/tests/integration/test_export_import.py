from pathlib import Path
from typing import Any, Dict

import pytest
import ujson

from infrahub_sdk import InfrahubClient
from infrahub_sdk.ctl.exporter import LineDelimitedJSONExporter
from infrahub_sdk.ctl.importer import LineDelimitedJSONImporter
from infrahub_sdk.exceptions import SchemaNotFoundError
from infrahub_sdk.transfer.exceptions import TransferFileNotFoundError
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter
from tests.helpers.test_app import TestInfrahubApp

PERSON_KIND = "TestingPerson"
POOL_KIND = "TestingPool"
CAR_KIND = "TestingCar"
MANUFACTURER_KIND = "TestingManufacturer"
TAG_KIND = "TestingTag"

# pylint: disable=unused-argument


class TestSchemaExportImportBase(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def temporary_directory(self, tmp_path_factory) -> Path:
        return tmp_path_factory.mktemp("infrahub-integration-tests")

    @pytest.fixture(scope="class")
    def schema_person_base(self) -> Dict[str, Any]:
        return {
            "name": "Person",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Person",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "height", "kind": "Number", "optional": True},
            ],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"}
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_base(self) -> Dict[str, Any]:
        return {
            "name": "Car",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Car",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "color", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": "TestingPerson",
                    "cardinality": "one",
                },
                {
                    "name": "manufacturer",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": "TestingManufacturer",
                    "cardinality": "one",
                    "identifier": "car__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_manufacturer_base(self) -> Dict[str, Any]:
        return {
            "name": "Manufacturer",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Manufacturer",
            "attributes": [{"name": "name", "kind": "Text"}, {"name": "description", "kind": "Text", "optional": True}],
            "relationships": [
                {
                    "name": "cars",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingCar",
                    "cardinality": "many",
                    "identifier": "car__manufacturer",
                },
                {
                    "name": "customers",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingPerson",
                    "cardinality": "many",
                    "identifier": "person__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_tag_base(self) -> Dict[str, Any]:
        return {
            "name": "Tag",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Testing Tag",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {"name": "cars", "kind": "Generic", "optional": True, "peer": "TestingCar", "cardinality": "many"},
                {
                    "name": "persons",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingPerson",
                    "cardinality": "many",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema(self, schema_car_base, schema_person_base, schema_manufacturer_base, schema_tag_base) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_base, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(self, client: InfrahubClient, schema):
        await client.schema.load(schemas=[schema])

        john = await client.create(
            kind=PERSON_KIND, data=dict(name="John", height=175, description="The famous Joe Doe")
        )
        await john.save()

        jane = await client.create(
            kind=PERSON_KIND, data=dict(name="Jane", height=165, description="The famous Jane Doe")
        )
        await jane.save()

        honda = await client.create(kind=MANUFACTURER_KIND, data=dict(name="honda", description="Honda Motor Co., Ltd"))
        await honda.save()

        renault = await client.create(
            kind=MANUFACTURER_KIND,
            data=dict(name="renault", description="Groupe Renault is a French multinational automobile manufacturer"),
        )
        await renault.save()

        accord = await client.create(
            kind=CAR_KIND,
            data=dict(name="accord", description="Honda Accord", color="#3443eb", manufacturer=honda, owner=jane),
        )
        await accord.save()

        civic = await client.create(
            kind=CAR_KIND,
            data=dict(name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=jane),
        )
        await civic.save()

        megane = await client.create(
            kind=CAR_KIND,
            data=dict(name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john),
        )
        await megane.save()

        blue = await client.create(kind=TAG_KIND, data=dict(name="blue", cars=[accord, civic], persons=[jane]))
        await blue.save()

        red = await client.create(kind=TAG_KIND, data=dict(name="red", persons=[john]))
        await red.save()

        objs = {
            "john": john.id,
            "jane": jane.id,
            "honda": honda.id,
            "renault": renault.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
            "blue": blue.id,
            "red": red.id,
        }

        return objs

    def reset_export_directory(self, temporary_directory: Path):
        for file in temporary_directory.iterdir():
            if file.is_file():
                file.unlink()

    async def test_step01_export_no_schema(self, client: InfrahubClient, temporary_directory: Path):
        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        nodes_file = temporary_directory / "nodes.json"
        relationships_file = temporary_directory / "relationships.json"

        # Export should create files even if they do not really hold any data
        assert nodes_file.exists()
        assert relationships_file.exists()

        # Verify that only the admin account has been exported
        with nodes_file.open() as f:
            admin_account_node_dump = ujson.loads(f.readline())
        assert admin_account_node_dump
        assert admin_account_node_dump["kind"] == "CoreAccount"
        assert ujson.loads(admin_account_node_dump["graphql_json"])["name"]["value"] == "admin"

        relationships_dump = ujson.loads(relationships_file.read_text())
        assert relationships_dump

    async def test_step02_import_no_schema(self, client: InfrahubClient, temporary_directory: Path):
        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # Schema should not be present
        for kind in (PERSON_KIND, CAR_KIND, MANUFACTURER_KIND, TAG_KIND):
            with pytest.raises(SchemaNotFoundError):
                await client.all(kind=kind)

        # Cleanup for next tests
        self.reset_export_directory(temporary_directory)

    async def test_step03_export_empty_dataset(self, client: InfrahubClient, temporary_directory: Path, schema):
        await client.schema.load(schemas=[schema])

        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        nodes_file = temporary_directory / "nodes.json"
        relationships_file = temporary_directory / "relationships.json"

        # Export should create files even if they do not really hold any data
        assert nodes_file.exists()
        assert relationships_file.exists()

        # Verify that only the admin account has been exported
        with nodes_file.open() as f:
            admin_account_node_dump = ujson.loads(f.readline())
        assert admin_account_node_dump
        assert admin_account_node_dump["kind"] == "CoreAccount"
        assert ujson.loads(admin_account_node_dump["graphql_json"])["name"]["value"] == "admin"

        relationships_dump = ujson.loads(relationships_file.read_text())
        assert relationships_dump

    async def test_step04_import_empty_dataset(self, client: InfrahubClient, temporary_directory: Path, schema):
        await client.schema.load(schemas=[schema])

        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # No data for any kind should be retrieved
        for kind in (PERSON_KIND, CAR_KIND, MANUFACTURER_KIND, TAG_KIND):
            assert not await client.all(kind=kind)

        # Cleanup for next tests
        self.reset_export_directory(temporary_directory)

    async def test_step05_export_initial_dataset(
        self, client: InfrahubClient, temporary_directory: Path, initial_dataset
    ):
        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        nodes_file = temporary_directory / "nodes.json"
        relationships_file = temporary_directory / "relationships.json"

        # Export should create files
        assert nodes_file.exists()
        assert relationships_file.exists()

        # Verify that nodes have been exported
        nodes_dump = []
        with nodes_file.open() as reader:
            while line := reader.readline():
                nodes_dump.append(ujson.loads(line))
        assert len(nodes_dump) == len(initial_dataset) + 5  # add number to account for default data

        relationships_dump = ujson.loads(relationships_file.read_text())
        assert relationships_dump

    async def test_step06_import_initial_dataset(self, client: InfrahubClient, temporary_directory: Path, schema):
        await client.schema.load(schemas=[schema])

        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # Each kind must have nodes
        for kind in (PERSON_KIND, CAR_KIND, MANUFACTURER_KIND, TAG_KIND):
            assert await client.all(kind=kind)

    async def test_step07_import_initial_dataset_with_existing_data(
        self, client: InfrahubClient, temporary_directory: Path, initial_dataset
    ):
        # Count existing nodes
        counters: Dict[str, int] = {}
        for kind in (PERSON_KIND, CAR_KIND, MANUFACTURER_KIND, TAG_KIND):
            nodes = await client.all(kind=kind)
            counters[kind] = len(nodes)

        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # Nodes must not be duplicated
        for kind in (PERSON_KIND, CAR_KIND, MANUFACTURER_KIND, TAG_KIND):
            nodes = await client.all(kind=kind)
            assert len(nodes) == counters[kind]

        # Cleanup for next tests
        self.reset_export_directory(temporary_directory)

    async def test_step99_import_wrong_drectory(self, client: InfrahubClient):
        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        # Using a directory that does not exist, should lead to exception
        with pytest.raises(TransferFileNotFoundError):
            await importer.import_data(import_directory=Path("this_directory_does_not_exist"), branch="main")


class TestSchemaExportImportManyRelationships(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def temporary_directory(self, tmp_path_factory) -> Path:
        return tmp_path_factory.mktemp("infrahub-integration-tests")

    @pytest.fixture(scope="class")
    def schema_pool_base(self) -> Dict[str, Any]:
        return {
            "name": "Pool",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Pool",
            "attributes": [{"name": "name", "kind": "Text"}, {"name": "description", "kind": "Text", "optional": True}],
            "relationships": [
                {
                    "name": "cars",
                    "kind": "Attribute",
                    "optional": True,
                    "peer": "TestingCar",
                    "cardinality": "many",
                    "identifier": "car__pool",
                }
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_base(self) -> Dict[str, Any]:
        return {
            "name": "Car",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Car",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "color", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "pools",
                    "kind": "Attribute",
                    "optional": True,
                    "peer": "TestingPool",
                    "cardinality": "many",
                    "identifier": "car__pool",
                },
                {
                    "name": "manufacturer",
                    "kind": "Attribute",
                    "optional": False,
                    "peer": "TestingManufacturer",
                    "cardinality": "one",
                    "identifier": "car__manufacturer",
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_manufacturer_base(self) -> Dict[str, Any]:
        return {
            "name": "Manufacturer",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Manufacturer",
            "attributes": [{"name": "name", "kind": "Text"}, {"name": "description", "kind": "Text", "optional": True}],
            "relationships": [
                {
                    "name": "cars",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingCar",
                    "cardinality": "many",
                    "identifier": "car__manufacturer",
                }
            ],
        }

    @pytest.fixture(scope="class")
    def schema(self, schema_car_base, schema_pool_base, schema_manufacturer_base) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_pool_base, schema_car_base, schema_manufacturer_base],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(self, client: InfrahubClient, schema):  # noqa: PLR0914
        await client.schema.load(schemas=[schema])

        bmw = await client.create(
            kind=MANUFACTURER_KIND,
            data=dict(
                name="BMW",
                description="Bayerische Motoren Werke AG is a German multinational manufacturer of luxury vehicles and motorcycles",
            ),
        )
        await bmw.save()

        fiat = await client.create(
            kind=MANUFACTURER_KIND,
            data=dict(name="Fiat", description="Fiat Automobiles S.p.A. is an Italian automobile manufacturer"),
        )
        await fiat.save()

        five_series = await client.create(
            kind=CAR_KIND, data=dict(name="5 series", description="BMW 5 series", color="#000000", manufacturer=bmw)
        )
        await five_series.save()

        five_hundred = await client.create(
            kind=CAR_KIND, data=dict(name="500", description="Fiat 500", color="#540302", manufacturer=fiat)
        )
        await five_hundred.save()

        premium = await client.create(
            kind=POOL_KIND, data=dict(name="Premium", description="Premium cars", cars=[five_series])
        )
        await premium.save()

        compact = await client.create(
            kind=POOL_KIND, data=dict(name="Compact", description="Compact cars", cars=[five_hundred])
        )
        await compact.save()

        sedan = await client.create(
            kind=POOL_KIND, data=dict(name="Sedan", description="Sedan cars", cars=[five_series])
        )
        await sedan.save()

        city_cars = await client.create(
            kind=POOL_KIND, data=dict(name="City", description="City cars", cars=[five_hundred])
        )
        await city_cars.save()

        objs = {
            "bmw": bmw.id,
            "fiat": fiat.id,
            "5series": five_series.id,
            "500": five_hundred.id,
            "premium": premium.id,
            "compact": compact.id,
            "sedan": sedan.id,
            "city_cars": city_cars.id,
        }

        return objs

    def reset_export_directory(self, temporary_directory: Path):
        for file in temporary_directory.iterdir():
            if file.is_file():
                file.unlink()

    async def test_step01_export_initial_dataset(
        self, client: InfrahubClient, temporary_directory: Path, initial_dataset
    ):
        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        nodes_file = temporary_directory / "nodes.json"
        relationships_file = temporary_directory / "relationships.json"

        # Export should create files
        assert nodes_file.exists()
        assert relationships_file.exists()

        # Verify that nodes have been exported
        nodes_dump = []
        with nodes_file.open() as reader:
            while line := reader.readline():
                nodes_dump.append(ujson.loads(line))
        assert len(nodes_dump) == len(initial_dataset) + 5  # add number to account for default data

        # Make sure there are as many relationships as there are in the database
        relationship_count = 0
        for node in await client.all(kind=POOL_KIND):
            await node.cars.fetch()
            relationship_count += len(node.cars.peers)
        relationships_dump = ujson.loads(relationships_file.read_text())
        assert len(relationships_dump) == relationship_count + 1  # add number to account for default data

    async def test_step02_import_initial_dataset(self, client: InfrahubClient, temporary_directory: Path, schema):
        await client.schema.load(schemas=[schema])

        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # Each kind must have nodes
        for kind in (POOL_KIND, CAR_KIND, MANUFACTURER_KIND):
            assert await client.all(kind=kind)

        # Make sure relationships were properly imported
        relationship_count = 0
        for node in await client.all(kind=POOL_KIND):
            await node.cars.fetch()
            relationship_count += len(node.cars.peers)
        relationships_file = temporary_directory / "relationships.json"
        relationships_dump = ujson.loads(relationships_file.read_text())
        assert len(relationships_dump) == relationship_count + 1  # add number to account for default data

    async def test_step03_import_initial_dataset_with_existing_data(
        self, client: InfrahubClient, temporary_directory: Path, initial_dataset
    ):
        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        # Each kind must have nodes
        for kind in (POOL_KIND, CAR_KIND, MANUFACTURER_KIND):
            assert await client.all(kind=kind)

        # Make sure relationships were properly imported
        relationship_count = 0
        for node in await client.all(kind=POOL_KIND):
            await node.cars.fetch()
            relationship_count += len(node.cars.peers)
        relationships_file = temporary_directory / "relationships.json"
        relationships_dump = ujson.loads(relationships_file.read_text())
        assert len(relationships_dump) == relationship_count + 1  # add number to account for default data

        # Cleanup for next tests
        self.reset_export_directory(temporary_directory)
