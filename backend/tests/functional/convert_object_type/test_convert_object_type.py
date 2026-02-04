from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.constants.infrahubkind import NUMBERPOOL
from infrahub.core.query.resource_manager import NumberPoolGetReserved
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

CONVERT_OBJECT_MUTATION = """
    mutation($node_id: String!, $target_kind: String!, $fields_mapping: GenericScalar!) {
        ConvertObjectType(data: {
                node_id: $node_id,
                target_kind: $target_kind,
                fields_mapping: $fields_mapping
            }) {
                ok
                node
        }
    }
"""


class TestGetConversionSchemaMapping(TestInfrahubApp):
    async def test_get_fields_mapping(self, client: InfrahubClient, schemas_conversion: dict) -> None:
        response = await client.schema.load(schemas=[schemas_conversion])
        assert len(response.errors) == 0, response.errors

        query = """ query($source_kind: String!, $target_kind: String!) {
                FieldsMappingTypeConversion(source_kind: $source_kind, target_kind: $target_kind) {
                    mapping
                }
            }
            """

        response = await client.execute_graphql(
            query=query,
            variables={
                "source_kind": "TestconvPerson1",
                "target_kind": "TestconvPerson2",
            },
            branch_name="main",
        )

        assert response == {
            "FieldsMappingTypeConversion": {
                "mapping": {
                    "citizenship": {"is_mandatory": False, "source_field_name": None, "relationship_cardinality": None},
                    "age": {"is_mandatory": True, "source_field_name": None, "relationship_cardinality": None},
                    "name": {"is_mandatory": True, "source_field_name": "name", "relationship_cardinality": None},
                    "height": {"is_mandatory": False, "source_field_name": "height", "relationship_cardinality": None},
                    "favorite_color": {
                        "is_mandatory": False,
                        "source_field_name": "favorite_color",
                        "relationship_cardinality": None,
                    },
                    "subscriber_of_groups": {
                        "is_mandatory": False,
                        "source_field_name": "subscriber_of_groups",
                        "relationship_cardinality": "many",
                    },
                    "slowest_cars": {
                        "is_mandatory": False,
                        "source_field_name": None,
                        "relationship_cardinality": "many",
                    },
                    "member_of_groups": {
                        "is_mandatory": False,
                        "source_field_name": "member_of_groups",
                        "relationship_cardinality": "many",
                    },
                    "profiles": {
                        "is_mandatory": False,
                        "source_field_name": "profiles",
                        "relationship_cardinality": "many",
                    },
                    "worst_car": {"is_mandatory": False, "source_field_name": None, "relationship_cardinality": "one"},
                    "favorite_car": {
                        "is_mandatory": False,
                        "source_field_name": "favorite_car",
                        "relationship_cardinality": "one",
                    },
                    "fastest_cars": {
                        "is_mandatory": False,
                        "source_field_name": "fastest_cars",
                        "relationship_cardinality": "many",
                    },
                    "bags": {"is_mandatory": False, "source_field_name": "bags", "relationship_cardinality": "many"},
                }
            }
        }


class TestConvertObjectType(TestInfrahubApp):
    async def test_convert_object_type(self, client: InfrahubClient, schemas_conversion: dict) -> None:
        response = await client.schema.load(schemas=[schemas_conversion])
        assert len(response.errors) == 0, response.errors

        car_1 = await client.create(kind="TestconvCar", name="car_1")
        await car_1.save()
        car_2 = await client.create(kind="TestconvCar", name="car_2")
        await car_2.save()
        car_3 = await client.create(kind="TestconvCar", name="car_3")
        await car_3.save()

        jack_1 = await client.create(
            kind="TestconvPerson1",
            name="Jack",
            height=170,
            favorite_color="green",
            favorite_car=car_1,
            fastest_cars=[car_1, car_2],
        )
        await jack_1.save()

        mapping = {
            "name": ConversionFieldInput(source_field="name"),
            "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=25)),
            "worst_car": ConversionFieldInput(data=ConversionFieldValue(peer_id=car_1.id)),
            "fastest_cars": ConversionFieldInput(source_field="fastest_cars"),
            "slowest_cars": ConversionFieldInput(data=ConversionFieldValue(peers_ids=[car_1.id])),
            "bags": ConversionFieldInput(data=ConversionFieldValue(peers_ids=[])),
            "favorite_color": ConversionFieldInput(use_default_value=True),
        }

        mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

        response = await client.execute_graphql(
            query=CONVERT_OBJECT_MUTATION,
            variables={
                "node_id": str(jack_1.id),
                "fields_mapping": mapping_dict,
                "target_kind": "TestconvPerson2",
            },
            branch_name="main",
        )
        assert response["ConvertObjectType"]["ok"] is True
        res_node = response["ConvertObjectType"]["node"]
        assert res_node["__kind__"] == "TestconvPerson2"
        assert res_node["age"]["value"] == 25
        assert res_node["name"]["value"] == "Jack"
        assert res_node["height"]["value"] == 170
        assert res_node["favorite_color"]["value"] == "blue"


class TestConvertObjectTypeResourcePool(TestInfrahubApp):
    async def _run_number_pool_validator(self, db: InfrahubDatabase) -> None:
        snpv = SchemaNumberPoolSynchronizer(db=db, log=MagicMock(), schema_manager=registry.schema)
        await snpv.run()

    @pytest.fixture
    async def schemas_person(self, node_group_schema: None, data_schema: None) -> SchemaRoot:
        person_generic = GenericSchema(
            name="PersonGeneric",
            namespace="Test",
            human_friendly_id=["name__value"],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="height", kind="Number", optional=True),
                AttributeSchema(name="random_id", kind="NumberPool", read_only=True),
            ],
        )

        person1 = NodeSchema(
            name="Person1",
            namespace="Test",
            inherit_from=[person_generic.kind],
        )

        person2 = NodeSchema(
            name="Person2",
            namespace="Test",
            inherit_from=[person_generic.kind],
            attributes=[
                AttributeSchema(name="age", kind="Number", default_value=25),
                AttributeSchema(name="citizenship", kind="Text", optional=True),
            ],
        )

        schema: SchemaRoot = SchemaRoot(version="1.0", generics=[person_generic], nodes=[person1, person2])
        return schema

    async def test_convert_number_pool(
        self, db: InfrahubDatabase, client: InfrahubClient, schemas_person: SchemaRoot, default_branch: Branch
    ) -> None:
        response = await client.schema.load(schemas=[schemas_person.model_dump()])
        assert len(response.errors) == 0, response.errors

        await self._run_number_pool_validator(db)

        # Create some objects
        persons: dict[str, InfrahubNode] = {}
        for name in ["jack", "paul", "pierre"]:
            person = await client.create(kind="TestPerson1", name=name)
            await person.save()
            persons[name] = person

        # Retrieve the pool used for the NumberPool attribute
        pools = await client.all(kind=NUMBERPOOL)
        assert len(pools) == 1
        pool = pools[0]

        # Check the state of the pool before converting the object
        query1 = await NumberPoolGetReserved.init(db=db, pool_id=pool.id, branch=default_branch)
        await query1.execute(db=db)
        reservations_before = {item.identifier: item.value for item in query1.get_reservations()}

        response = await client.execute_graphql(
            query=CONVERT_OBJECT_MUTATION,
            variables={
                "node_id": str(persons["jack"].id),
                "target_kind": "TestPerson2",
                "fields_mapping": {},
            },
            branch_name="main",
        )
        assert response["ConvertObjectType"]["ok"] is True
        new_id = response["ConvertObjectType"]["node"]["id"]

        query1 = await NumberPoolGetReserved.init(db=db, pool_id=pool.id, branch=default_branch)
        await query1.execute(db=db)
        reservations_after = {item.identifier: item.value for item in query1.get_reservations()}

        assert reservations_after[new_id] == reservations_before[str(persons["jack"].id)]
