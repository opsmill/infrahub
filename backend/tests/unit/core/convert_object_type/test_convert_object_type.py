from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node.convert_object_kind.convert_object_kind import (
    InputDataForDestField,
    InputForDestField,
    convert_object_type,
)
from infrahub.core.node.convert_object_kind.schema_mapping import SchemaMappingValue, get_schema_mapping
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import NodeNotFoundError, ValidationError
from tests.helpers.test_app import TestInfrahubApp
from tests.node_creation import create_and_save

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def register_schemas_conversion(db: InfrahubDatabase, default_branch: Branch, schemas_conversion) -> SchemaBranch:
    schema_root = SchemaRoot(**schemas_conversion)
    return registry.schema.register_schema(schema=schema_root, branch=default_branch.name)


class TestConvertObjectType(TestInfrahubApp):
    def test_schema_conversion_mapping(
        self, db: InfrahubDatabase, client: InfrahubClient, register_schemas_conversion, branch
    ):
        mapping = get_schema_mapping(source_kind="TestPerson1", target_kind="TestPerson2", branch=branch.name)
        assert len(mapping) == 12
        assert mapping["name"] == SchemaMappingValue(source_field_name="name", is_mandatory=None)
        assert mapping["height"] == SchemaMappingValue(source_field_name="height", is_mandatory=None)
        assert mapping["age"] == SchemaMappingValue(source_field_name=None, is_mandatory=True)
        assert mapping["citizenship"] == SchemaMappingValue(source_field_name=None, is_mandatory=False)

        assert mapping["favorite_car"] == SchemaMappingValue(
            source_field_name="favorite_car", relationship_cardinality=RelationshipCardinality.ONE
        )
        assert mapping["worst_car"] == SchemaMappingValue(
            is_mandatory=False, relationship_cardinality=RelationshipCardinality.ONE
        )
        assert mapping["fastest_cars"] == SchemaMappingValue(
            source_field_name="fastest_cars", relationship_cardinality=RelationshipCardinality.MANY
        )
        assert mapping["slowest_cars"] == SchemaMappingValue(
            is_mandatory=False, relationship_cardinality=RelationshipCardinality.MANY
        )
        assert mapping["bags"] == SchemaMappingValue(
            source_field_name="bags", relationship_cardinality=RelationshipCardinality.MANY
        )

        # Not entirely sure how these ones should be mapped UI side,
        assert mapping["member_of_groups"] == SchemaMappingValue(
            source_field_name="member_of_groups",
            relationship_cardinality=RelationshipCardinality.MANY,
        )
        assert mapping["subscriber_of_groups"] == SchemaMappingValue(
            source_field_name="subscriber_of_groups",
            relationship_cardinality=RelationshipCardinality.MANY,
        )
        assert mapping["profiles"] == SchemaMappingValue(
            source_field_name="profiles",
            relationship_cardinality=RelationshipCardinality.MANY,
        )

    async def test_convert_object_type(
        self, db: InfrahubDatabase, client: InfrahubClient, register_schemas_conversion, branch
    ) -> None:
        # TODO e2e test with interface L2 / L3 schemas.
        # create L2
        # convert to L3
        # make sure L2 deleted, L3 created, attributes matches
        # do it in a unit way first. Test multiple cases in unit
        # then we'll do and e2e test with the API.
        # models_path = "/Users/lucas/infrahub/models/base"
        # schema_data = SchemaFile.load_from_disk(paths=[Path(models_path)])
        # response = await client.schema.load(schemas=[item.content for item in schema_data])
        # assert len(response.errors) == 0, response.errors

        # TODO special mutate_create like repos?

        # TODO branch agnostic / aware?

        car_1 = await create_and_save(db=db, schema="TestCar", name="car_1", branch=branch)
        car_2 = await create_and_save(db=db, schema="TestCar", name="car_2", branch=branch)
        car_3 = await create_and_save(db=db, schema="TestCar", name="car_3", branch=branch)

        jack_1 = await create_and_save(
            db=db,
            schema="TestPerson1",
            name=f"Jack-{branch.name}",
            height=170,
            favorite_car=car_1,
            fastest_cars=[car_1, car_2],
            branch=branch,
        )

        # Bag `owner` is a mandatory relationship. Deleting the owner without cascade delete will temporary
        # put this relationship in an invalid state as bag would have no owner, but then creating the new person
        # node with this bag will fix it.
        bag = await create_and_save(db=db, schema="TestBag", name="bag-1", owner=jack_1, branch=branch)

        # Refresh jack_1 now that we added a bag
        jack_1 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_1.id, kind="TestPerson1", prefetch_relationships=True, branch=branch
        )

        mapping = {
            "name": InputForDestField(source_field="name"),
            "height": InputForDestField(source_field="height"),
            "age": InputForDestField(data=InputDataForDestField(attribute_value=25)),
            "favorite_car": InputForDestField(source_field="favorite_car"),
            "worst_car": InputForDestField(data=InputDataForDestField(peer_id=car_3.id)),
            "fastest_cars": InputForDestField(source_field="fastest_cars"),
            "slowest_cars": InputForDestField(data=InputDataForDestField(peers_ids=[car_3.id])),
            "bags": InputForDestField(source_field="bags"),
        }

        jack_2 = await convert_object_type(
            node=jack_1, target_kind="TestPerson2", mapping=mapping, db=db, branch=branch
        )

        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one_by_id_or_default_filter(db=db, id=jack_1.id, kind="TestPerson1", branch=branch)

        jack_2 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_2.id, kind="TestPerson2", prefetch_relationships=True, branch=branch
        )
        assert jack_2 is not None
        assert jack_2.name.value == jack_1.name.value
        assert jack_2.height.value == jack_1.height.value
        assert jack_2.age.value == 25
        assert jack_2.citizenship.value is None

        assert (await jack_2.favorite_car.get_peer(db=db)).id == car_1.id
        assert (await jack_2.worst_car.get_peer(db=db)).id == car_3.id
        assert sorted([node.id for _, node in (await jack_2.fastest_cars.get_peers(db=db)).items()]) == sorted(
            [car_1.id, car_2.id]
        )
        assert sorted([node.id for _, node in (await jack_2.slowest_cars.get_peers(db=db)).items()]) == sorted(
            [car_3.id]
        )
        assert sorted([node.id for _, node in (await jack_2.bags.get_peers(db=db)).items()]) == sorted([bag.id])

        # Make sure node retrieval
        for node in [car_1, car_2, car_3, bag]:
            await NodeManager.get_one_by_id_or_default_filter(
                db=db, id=node.id, kind=node.get_kind(), prefetch_relationships=True, branch=branch
            )

    async def test_raise_on_break_mandatory_relationship(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_conversion_mandatory_owner, default_branch
    ) -> None:
        # Add a mandatory relationship between TestPerson1 and TestCar, that would no longer exist after converting a TestPerson1 to a TestPerson2.
        # TODO also test when rel is defined only on TestPerson1 side

        registry.schema.register_schema(
            schema=SchemaRoot(**schema_conversion_mandatory_owner), branch=default_branch.name
        )

        jack_1 = await create_and_save(
            db=db,
            schema="TestPerson1",
            name=f"Jack-{default_branch.name}",
            branch=default_branch,
        )

        car_1 = await create_and_save(
            db=db, schema="TestCar", name="car_1", branch=default_branch, mandatory_owner=jack_1
        )

        # Refresh jack_1 now that we added a bag
        jack_1 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_1.id, kind="TestPerson1", prefetch_relationships=True, branch=default_branch
        )

        mapping = {
            "name": InputForDestField(source_field="name"),
        }

        with pytest.raises(ValidationError, match=r"Too few relationships, min 1 at mandatory_owner"):
            await convert_object_type(
                node=jack_1, target_kind="TestPerson2", mapping=mapping, db=db, branch=default_branch
            )

        # And make sure it works when setting a new owner to the car
        mapping = {
            "name": InputForDestField(source_field="name"),
            "my_car": InputForDestField(data=InputDataForDestField(peer_id=car_1.id)),
        }
        await convert_object_type(node=jack_1, target_kind="TestPerson2", mapping=mapping, db=db, branch=default_branch)

    async def test_agnostic_attributes(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_conversion_aware_agnostic, default_branch
    ) -> None:
        registry.schema.register_schema(
            schema=SchemaRoot(**schema_conversion_aware_agnostic), branch=default_branch.name
        )

        jack_1 = await create_and_save(
            db=db,
            schema="TestPerson1",
            name_agnostic=f"Jack-{default_branch.name}",
            age_1_agnostic=25,
            height_1_aware=180,
            branch=default_branch,
        )

        mapping = {
            "name_agnostic": InputForDestField(source_field="name_agnostic"),
            "age_2_aware": InputForDestField(source_field="age_1_agnostic"),
            "height_2_agnostic": InputForDestField(source_field="height_1_aware"),
        }

        jack_2 = await convert_object_type(
            node=jack_1, target_kind="TestPerson2", mapping=mapping, db=db, branch=default_branch
        )

        assert jack_2 is not None
        assert jack_2.name_agnostic.value == jack_1.name_agnostic.value
        assert jack_2.height_2_agnostic.value == jack_1.height_1_aware.value
        assert jack_2.age_2_aware.value == jack_1.age_1_agnostic.value
