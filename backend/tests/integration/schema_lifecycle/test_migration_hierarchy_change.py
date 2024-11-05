import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

PERSON_KIND = "TestingPerson"
CAR_KIND = "TestingCar"
MANUFACTURER_KIND_01 = "TestingManufacturer"
MANUFACTURER_KIND_03 = "TestingCarMaker"
TAG_KIND = "TestingTag"


class TestSchemaLifecycleBase(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_location_generic(self) -> GenericSchema:
        return GenericSchema(
            name="Generic",
            namespace="Location",
            hierarchical=True,
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )

    @pytest.fixture(scope="class")
    def schema_location_country(self) -> NodeSchema:
        return NodeSchema(
            name="Country", namespace="Location", inherit_from=["LocationGeneric"], children="LocationSite", parent=""
        )

    @pytest.fixture(scope="class")
    def schema_location_site(self) -> NodeSchema:
        return NodeSchema(
            name="Site", namespace="Location", inherit_from=["LocationGeneric"], children="", parent="LocationCountry"
        )

    @pytest.fixture(scope="class")
    async def location_schema_01(
        self,
        schema_location_generic: GenericSchema,
        schema_location_country: NodeSchema,
        schema_location_site: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0", generics=[schema_location_generic], nodes=[schema_location_country, schema_location_site]
        )

    @pytest.fixture(scope="class")
    def schema_location_country_02(self) -> NodeSchema:
        return NodeSchema(
            name="Country",
            namespace="Location",
            inherit_from=["LocationGeneric"],
            children="LocationMetro",
            parent=None,
        )

    @pytest.fixture(scope="class")
    def schema_location_metro_02(self) -> NodeSchema:
        return NodeSchema(
            name="Metro",
            namespace="Location",
            inherit_from=["LocationGeneric"],
            children="LocationSite",
            parent="LocationCountry",
        )

    @pytest.fixture(scope="class")
    def schema_location_site_02(self) -> NodeSchema:
        return NodeSchema(
            name="Site", namespace="Location", inherit_from=["LocationGeneric"], children=None, parent="LocationMetro"
        )

    @pytest.fixture(scope="class")
    async def location_schema_02(
        self,
        schema_location_generic: GenericSchema,
        schema_location_country_02: NodeSchema,
        schema_location_site_02: NodeSchema,
        schema_location_metro_02: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            generics=[schema_location_generic],
            nodes=[schema_location_country_02, schema_location_metro_02, schema_location_site_02],
        )

    @pytest.fixture(scope="class")
    async def initial_schema(
        self, db: InfrahubDatabase, initialize_registry, default_branch: Branch, location_schema_01: SchemaRoot
    ) -> None:
        branch_schema = registry.schema.get_schema_branch(name=default_branch.name)
        tmp_schema = branch_schema.duplicate()
        tmp_schema.load_schema(schema=location_schema_01)
        tmp_schema.process()

        await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def branch_1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch_1")

    async def test_baseline(
        self, db: InfrahubDatabase, client: InfrahubClient, initial_schema: dict[str, Node]
    ) -> None:
        country_schema = await client.schema.get(kind="LocationCountry")
        rels_by_name = {r.name: r for r in country_schema.relationships}
        assert rels_by_name["parent"].peer == "LocationGeneric"
        assert rels_by_name["children"].peer == "LocationSite"
        site_schema = await client.schema.get(kind="LocationSite")
        rels_by_name = {r.name: r for r in site_schema.relationships}
        assert rels_by_name["parent"].peer == "LocationCountry"
        assert rels_by_name["children"].peer == "LocationGeneric"

    async def test_check_schema_02(self, client: InfrahubClient, branch_1: Branch, location_schema_02: SchemaRoot):
        success, response = await client.schema.check(
            schemas=[location_schema_02.model_dump(mode="json")], branch=branch_1.name
        )
        assert success
        assert response == {
            "diff": {
                "added": {"LocationMetro": {"added": {}, "changed": {}, "removed": {}}},
                "removed": {},
                "changed": {
                    "LocationSite": {
                        "added": {},
                        "removed": {},
                        "changed": {
                            "parent": None,
                            "relationships": {
                                "added": {},
                                "removed": {},
                                "changed": {"parent": {"added": {}, "removed": {}, "changed": {"peer": None}}},
                            },
                        },
                    },
                    "LocationCountry": {
                        "added": {},
                        "removed": {},
                        "changed": {
                            "children": None,
                            "relationships": {
                                "added": {},
                                "removed": {},
                                "changed": {"children": {"added": {}, "removed": {}, "changed": {"peer": None}}},
                            },
                        },
                    },
                    "LocationGeneric": {"added": {}, "changed": {"used_by": None}, "removed": {}},
                },
            },
        }

    async def test_load_schema_02(
        self, db: InfrahubDatabase, client: InfrahubClient, branch_1: Branch, location_schema_02: SchemaRoot
    ):
        response = await client.schema.load(schemas=[location_schema_02.model_dump(mode="json")], branch=branch_1.name)
        assert not response.errors

        country_schema = await client.schema.get(kind="LocationCountry", branch=branch_1.name)
        rels_by_name = {r.name: r for r in country_schema.relationships}
        assert rels_by_name["parent"].peer == "LocationGeneric"
        assert rels_by_name["children"].peer == "LocationMetro"
        metro_schema = await client.schema.get(kind="LocationMetro", branch=branch_1.name)
        rels_by_name = {r.name: r for r in metro_schema.relationships}
        assert rels_by_name["parent"].peer == "LocationCountry"
        assert rels_by_name["children"].peer == "LocationSite"
        site_schema = await client.schema.get(kind="LocationSite", branch=branch_1.name)
        rels_by_name = {r.name: r for r in site_schema.relationships}
        assert rels_by_name["parent"].peer == "LocationMetro"
        assert rels_by_name["children"].peer == "LocationGeneric"

        country_schema = db.schema.get(name="LocationCountry", branch=branch_1, duplicate=False)
        assert country_schema.parent == ""  # noqa: PLC1901
        assert country_schema.children == "LocationMetro"
        metro_schema = db.schema.get(name="LocationMetro", branch=branch_1, duplicate=False)
        assert metro_schema.parent == "LocationCountry"
        assert metro_schema.children == "LocationSite"
        site_schema = db.schema.get(name="LocationSite", branch=branch_1, duplicate=False)
        assert site_schema.parent == "LocationMetro"
        assert site_schema.children == ""  # noqa: PLC1901
