from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GLOBAL_BRANCH_NAME, RelationshipCardinality
from infrahub.core.convert_object_type.object_conversion import (
    ConversionFieldInput,
    ConversionFieldValue,
    convert_and_validate_object_type,
)
from infrahub.core.convert_object_type.schema_mapping import SchemaMappingValue, get_schema_mapping
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError, ValidationError
from tests.helpers.test_app import TestInfrahubApp
from tests.node_creation import create_and_save

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestSchemaConversionMapping(TestInfrahubApp):
    async def test_schema_conversion_mapping(
        self, db: InfrahubDatabase, client: InfrahubClient, branch, schemas_conversion
    ) -> None:
        res = await client.schema.load(schemas=[schemas_conversion], branch=branch.name)
        assert len(res.errors) == 0, res.errors

        source_schema = registry.get_node_schema(name="TestconvPerson1", branch=branch)
        target_schema = registry.get_node_schema(name="TestconvPerson2", branch=branch)
        mapping = get_schema_mapping(source_schema=source_schema, target_schema=target_schema)
        assert len(mapping) == 13
        assert mapping["name"] == SchemaMappingValue(source_field_name="name", is_mandatory=True)
        assert mapping["height"] == SchemaMappingValue(source_field_name="height", is_mandatory=False)
        assert mapping["age"] == SchemaMappingValue(source_field_name=None, is_mandatory=True)
        assert mapping["citizenship"] == SchemaMappingValue(source_field_name=None, is_mandatory=False)
        assert mapping["favorite_color"] == SchemaMappingValue(
            source_field_name="favorite_color", relationship_cardinality=None, is_mandatory=False
        )
        assert mapping["favorite_car"] == SchemaMappingValue(
            source_field_name="favorite_car", relationship_cardinality=RelationshipCardinality.ONE, is_mandatory=False
        )
        assert mapping["worst_car"] == SchemaMappingValue(
            is_mandatory=False, relationship_cardinality=RelationshipCardinality.ONE
        )
        assert mapping["fastest_cars"] == SchemaMappingValue(
            source_field_name="fastest_cars", relationship_cardinality=RelationshipCardinality.MANY, is_mandatory=False
        )
        assert mapping["slowest_cars"] == SchemaMappingValue(
            is_mandatory=False, relationship_cardinality=RelationshipCardinality.MANY
        )
        assert mapping["bags"] == SchemaMappingValue(
            source_field_name="bags", relationship_cardinality=RelationshipCardinality.MANY, is_mandatory=False
        )

        assert mapping["member_of_groups"] == SchemaMappingValue(
            source_field_name="member_of_groups",
            relationship_cardinality=RelationshipCardinality.MANY,
            is_mandatory=False,
        )
        assert mapping["subscriber_of_groups"] == SchemaMappingValue(
            source_field_name="subscriber_of_groups",
            relationship_cardinality=RelationshipCardinality.MANY,
            is_mandatory=False,
        )
        assert mapping["profiles"] == SchemaMappingValue(
            source_field_name="profiles", relationship_cardinality=RelationshipCardinality.MANY, is_mandatory=False
        )


class TestConvertObjectType(TestInfrahubApp):
    async def test_convert_object_type(
        self, db: InfrahubDatabase, client: InfrahubClient, schemas_conversion, branch, service
    ) -> None:
        res = await client.schema.load(schemas=[schemas_conversion], branch=branch.name)
        assert len(res.errors) == 0, res.errors

        car_1 = await create_and_save(db=db, schema="TestconvCar", name="car_1", branch=branch)
        car_2 = await create_and_save(db=db, schema="TestconvCar", name="car_2", branch=branch)
        car_3 = await create_and_save(db=db, schema="TestconvCar", name="car_3", branch=branch)

        jack_1 = await create_and_save(
            db=db,
            schema="TestconvPerson1",
            name=f"Jack-{branch.name}",
            height=170,
            favorite_car=car_1,
            fastest_cars=[car_1, car_2],
            branch=branch,
        )

        # Bag `owner` is a mandatory relationship. Deleting the owner without cascade delete will temporary
        # put this relationship in an invalid state as bag would have no owner, but then creating the new person
        # node with this bag will fix it.
        bag = await create_and_save(db=db, schema="TestconvBag", name="bag-1", owner=jack_1, branch=branch)

        # Refresh jack_1 now that we added a bag
        jack_1 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_1.id, kind="TestconvPerson1", prefetch_relationships=True, branch=branch
        )

        mapping = {
            "name": ConversionFieldInput(source_field="name"),
            "height": ConversionFieldInput(source_field="height"),
            "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=25)),
            "favorite_car": ConversionFieldInput(source_field="favorite_car"),
            "worst_car": ConversionFieldInput(data=ConversionFieldValue(peer_id=car_3.id)),
            "fastest_cars": ConversionFieldInput(source_field="fastest_cars"),
            "slowest_cars": ConversionFieldInput(data=ConversionFieldValue(peers_ids=[car_3.id])),
            "bags": ConversionFieldInput(source_field="bags"),
        }

        person_2_schema = registry.get_node_schema(name="TestconvPerson2", branch=branch)
        jack_2 = await convert_and_validate_object_type(
            node=jack_1,
            target_schema=person_2_schema,
            mapping=mapping,
            db=db,
            branch=branch,
        )

        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one_by_id_or_default_filter(
                db=db, id=jack_1.id, kind="TestconvPerson1", branch=branch
            )

        jack_2 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_2.id, kind="TestconvPerson2", prefetch_relationships=True, branch=branch
        )
        assert jack_2 is not None
        assert jack_2.name.value == jack_1.name.value
        assert jack_2.height.value == jack_1.height.value
        assert jack_2.age.value == 25
        assert jack_2.favorite_color.value == "blue"
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

        # Make sure retrieving nodes works
        for node in [car_1, car_2, car_3, bag]:
            await NodeManager.get_one_by_id_or_default_filter(
                db=db, id=node.id, kind=node.get_kind(), prefetch_relationships=True, branch=branch
            )

    async def test_raise_on_break_mandatory_relationship(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_conversion_mandatory_owner, branch
    ) -> None:
        # Add a mandatory relationship between TestPerson1 and TestCar, that would no longer exist after converting a TestPerson1 to a TestPerson2.
        res = await client.schema.load(schemas=[schema_conversion_mandatory_owner], branch=branch.name)
        assert len(res.errors) == 0, res.errors

        jack_1 = await create_and_save(
            db=db,
            schema="TestmoPerson1",
            name=f"Jack-{branch.name}",
            branch=branch,
        )

        car_1 = await create_and_save(db=db, schema="TestmoCar", name="car_1", branch=branch, mandatory_owner=jack_1)

        # Refresh jack_1 now that we added a bag
        jack_1 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_1.id, kind="TestmoPerson1", prefetch_relationships=True, branch=branch
        )

        mapping = {
            "name": ConversionFieldInput(source_field="name"),
        }

        person_2_schema = registry.get_node_schema(name="TestmoPerson2", branch=branch)
        with pytest.raises(ValidationError, match=r"Too few relationships, min 1 at mandatory_owner"):
            await convert_and_validate_object_type(
                node=jack_1, target_schema=person_2_schema, mapping=mapping, db=db, branch=branch
            )

        # And make sure it works when setting a new owner to the car
        mapping = {
            "name": ConversionFieldInput(source_field="name"),
            "my_car": ConversionFieldInput(data=ConversionFieldValue(peer_id=car_1.id)),
        }
        await convert_and_validate_object_type(
            node=jack_1, target_schema=person_2_schema, mapping=mapping, db=db, branch=branch
        )

    async def test_raise_on_break_mandatory_unidirectional_relationship(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_conversion_unidirectional_relationships,
        default_branch,
        service,
    ) -> None:
        # Add a mandatory relationship between TestPerson1 and TestCar, that would no longer exist after converting a TestPerson1 to a TestPerson2.
        res = await client.schema.load(
            schemas=[schema_conversion_unidirectional_relationships], branch=default_branch.name
        )
        assert len(res.errors) == 0, res.errors

        jack_1 = await create_and_save(
            db=db,
            schema="TestudPerson1",
            name=f"Jack-{default_branch.name}",
            branch=default_branch,
        )

        _ = await create_and_save(
            db=db, schema="TestudCar", name="car_1", branch=default_branch, unidirectional_owner=jack_1
        )

        # Refresh jack_1 now that we added a car
        jack_1 = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=jack_1.id, kind="TestmoPerson1", prefetch_relationships=True, branch=default_branch
        )

        mapping = {
            "name": ConversionFieldInput(source_field="name"),
        }

        person_2_schema = registry.get_node_schema(name="TestudPerson2", branch=default_branch)
        with pytest.raises(ValidationError, match=r"Too few relationships, min 1 at unidirectional_owner"):
            await convert_and_validate_object_type(
                node=jack_1,
                target_schema=person_2_schema,
                mapping=mapping,
                db=db,
                branch=default_branch,
            )

    async def test_agnostic_attributes(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_conversion_aware_agnostic, default_branch, service
    ) -> None:
        res = await client.schema.load(schemas=[schema_conversion_aware_agnostic], branch=default_branch.name)
        assert len(res.errors) == 0, res.errors

        jack_1 = await create_and_save(
            db=db,
            schema="TestbsPerson1",
            name_agnostic=f"Jack-{default_branch.name}",
            age_1_agnostic=25,
            height_1_aware=180,
            branch=default_branch,
        )

        mapping = {
            "name_agnostic": ConversionFieldInput(source_field="name_agnostic"),
            "age_2_aware": ConversionFieldInput(source_field="age_1_agnostic"),
            "height_2_agnostic": ConversionFieldInput(source_field="height_1_aware"),
        }

        person_2_schema = registry.get_node_schema(name="TestbsPerson2", branch=default_branch)
        jack_2 = await convert_and_validate_object_type(
            node=jack_1,
            target_schema=person_2_schema,
            mapping=mapping,
            db=db,
            branch=default_branch,
        )

        assert jack_2 is not None
        assert jack_2.name_agnostic.value == jack_1.name_agnostic.value
        assert jack_2.height_2_agnostic.value == jack_1.height_1_aware.value
        assert jack_2.age_2_aware.value == jack_1.age_1_agnostic.value

    async def test_agnostic_node_with_aware_attributes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_conversion_agnostic_node_with_aware_attributes,
        default_branch,
    ) -> None:
        res = await client.schema.load(
            schemas=[schema_conversion_agnostic_node_with_aware_attributes], branch=default_branch.name
        )
        assert len(res.errors) == 0, res.errors

        car_1 = await create_and_save(
            db=db,
            schema="TestaaCar",
            name="car_1",
            branch=default_branch,
        )

        jack_1 = await create_and_save(
            db=db,
            schema="TestaaPerson1",
            name_agnostic="Jack",
            age_aware=25,
            favorite_car=car_1,
            other_cars=[car_1],
        )

        branch_name = "branch_convert_type"
        _ = await create_branch(branch_name=branch_name, db=db)

        mapping = {
            "name_agnostic": ConversionFieldInput(source_field="name_agnostic"),
            "age_aware": ConversionFieldInput(source_field="age_aware"),
            "height_aware": ConversionFieldInput(data=ConversionFieldValue(attribute_value=170)),
            "favorite_car": ConversionFieldInput(source_field="favorite_car"),
            "other_cars": ConversionFieldInput(source_field="other_cars"),
        }

        person_2_schema = registry.get_node_schema(name="TestaaPerson2", branch=default_branch)

        jack_2 = await convert_and_validate_object_type(
            node=jack_1,
            target_schema=person_2_schema,
            mapping=mapping,
            db=db,
            branch=default_branch,
        )

        with pytest.raises(NodeNotFoundError):
            await NodeManager.get_one_by_id_or_default_filter(
                db=db,
                id=jack_1.id,
                kind="TestaaPerson1",
            )

        assert jack_2 is not None
        assert jack_2.name_agnostic.value == jack_1.name_agnostic.value
        assert jack_2.age_aware.value == 25
        assert jack_2.height_aware.value == 170
        assert (await jack_2.favorite_car.get_peer(db=db)).id == car_1.id
        assert {node.id for _, node in (await jack_2.other_cars.get_peers(db=db)).items()} == {car_1.id}

        # Make sure other branches are in need rebase state
        br2 = await Branch.get_by_name(name=branch_name, db=db)
        assert br2.status == BranchStatus.NEED_REBASE.value

        # Make sure main/global branches are still in OPEN state
        main_branch = await Branch.get_by_name(name=registry.default_branch, db=db)
        assert main_branch.status == BranchStatus.OPEN.value
        global_branch = await Branch.get_by_name(name=GLOBAL_BRANCH_NAME, db=db)
        assert global_branch.status == BranchStatus.OPEN.value
