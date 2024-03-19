from pathlib import Path
from typing import Any, Dict

import pytest
import ujson

from infrahub_sdk import InfrahubClient
from infrahub_sdk.ctl.exporter import LineDelimitedJSONExporter
from infrahub_sdk.ctl.importer import LineDelimitedJSONImporter
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter
from tests.helpers.test_app import TestInfrahubApp

PERSON_KIND = "TestingPerson"
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

    async def test_step01_export_empty_dataset(self, client: InfrahubClient, temporary_directory: Path):
        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        assert (temporary_directory / "nodes.json").exists()
        assert (temporary_directory / "relationships.json").exists()

        assert (temporary_directory / "nodes.json").read_text()  # Only export the admin account
        assert ujson.loads((temporary_directory / "relationships.json").read_text()) == []

    async def test_step02_import_empty_dataset(self, client: InfrahubClient, temporary_directory: Path):
        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        assert (temporary_directory / "nodes.json").exists()
        assert (temporary_directory / "relationships.json").exists()

        assert (temporary_directory / "nodes.json").read_text()
        assert ujson.loads((temporary_directory / "relationships.json").read_text()) == []

    async def test_step03_export_with_dataset(self, client: InfrahubClient, temporary_directory: Path, initial_dataset):
        # FIXME: Find a a way to make a temp directory only for some steps
        for f in temporary_directory.iterdir():
            if f.is_file():
                f.unlink()

        exporter = LineDelimitedJSONExporter(client=client)
        await exporter.export(export_directory=temporary_directory, branch="main", namespaces=[])

        assert (temporary_directory / "nodes.json").exists()
        assert (temporary_directory / "relationships.json").exists()

        assert (temporary_directory / "nodes.json").read_text()  # Only export the admin account
        assert ujson.loads((temporary_directory / "relationships.json").read_text()) == []

    async def test_step04_import_with_dataset(self, client: InfrahubClient, temporary_directory: Path, initial_dataset):
        importer = LineDelimitedJSONImporter(client=client, topological_sorter=InfrahubSchemaTopologicalSorter())
        await importer.import_data(import_directory=temporary_directory, branch="main")

        assert (temporary_directory / "nodes.json").exists()
        assert (temporary_directory / "relationships.json").exists()

        assert (temporary_directory / "nodes.json").read_text()
        assert ujson.loads((temporary_directory / "relationships.json").read_text()) == []
