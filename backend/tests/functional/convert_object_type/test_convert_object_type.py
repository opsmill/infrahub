from __future__ import annotations

import json
from typing import TYPE_CHECKING

from infrahub.core.convert_object_type.conversion import InputDataForDestField, InputForDestField
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


class TestGetConversionSchemaMapping(TestInfrahubApp):
    async def test_get_fields_mapping(self, client: InfrahubClient, schemas_conversion) -> None:
        response = await client.schema.load(schemas=[schemas_conversion])
        assert len(response.errors) == 0, response.errors

        query = """ query($source_kind: String!, $target_kind: String!, $branch: String!) {
                FieldMappingTypeConversion(source_kind: $source_kind, target_kind: $target_kind, branch: $branch) {
                    mapping
                }
            }
            """

        response = await client.execute_graphql(
            query=query,
            variables={
                "branch": "main",
                "source_kind": "TestconvPerson1",
                "target_kind": "TestconvPerson2",
            },
        )

        print(f"{response=}")
        # TODO load result and assert values are ok


class TestConvertObjectType(TestInfrahubApp):
    async def test_convert_object_type(self, client: InfrahubClient, schemas_conversion) -> None:
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
            favorite_car=car_1,
            fastest_cars=[car_1, car_2],
        )

        await jack_1.save()

        query = """
            mutation($node_id: String!, $target_kind: String!, $branch: String!, $fields_mapping: JSONString!) {
                ConvertObjectType(data: {
                        node_id: $node_id,
                        target_kind: $target_kind,
                        branch: $branch,
                        fields_mapping: $fields_mapping
                    }) {
                        ok
                }
            }
        """

        mapping = {
            "name": InputForDestField(source_field="name"),
            "height": InputForDestField(source_field="height"),
            "age": InputForDestField(data=InputDataForDestField(attribute_value=25)),
            "favorite_car": InputForDestField(source_field="favorite_car"),
            "worst_car": InputForDestField(data=InputDataForDestField(peer_id=car_1.id)),
            "fastest_cars": InputForDestField(source_field="fastest_cars"),
            "slowest_cars": InputForDestField(data=InputDataForDestField(peers_ids=[car_1.id])),
            "bags": InputForDestField(data=InputDataForDestField(peers_ids=[])),
        }

        mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

        response = await client.execute_graphql(
            query=query,
            variables={
                "branch": "main",
                "node_id": str(jack_1.id),
                "fields_mapping": json.dumps(mapping_dict),
                "target_kind": "TestconvPerson2",
            },
        )

        print(f"{response=}")
        # TODO assert response...
