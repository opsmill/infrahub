from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState, RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.definitions.core.artifact import core_artifact_target
from infrahub.core.schema.definitions.core.lineage import lineage_owner, lineage_source
from tests.helpers.schema import CAR_SCHEMA, SNOW_TICKET_SCHEMA, load_schema
from tests.helpers.schema.car import CAR
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.branch import BranchData
    from infrahub_sdk.node.node import InfrahubNode

    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


class TestLoadOnBranchAndMain(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> None:
        internal_schema_root = SchemaRoot(version="1.0", generics=[lineage_source, lineage_owner, core_artifact_target])
        await load_schema(db=db, schema=internal_schema_root, branch_name=default_branch.name, update_db=True)

        schema_root = CAR_SCHEMA.duplicate()
        schema_root.version = "1.0"
        response = await client.schema.load(schemas=[schema_root.model_dump()])
        assert len(response.errors) == 0, response.errors

    @pytest.fixture(scope="class")
    async def car_schema_updated(self) -> NodeSchema:
        car_schema = CAR.model_copy(deep=True)
        car_schema.attributes.append(AttributeSchema(name="smell", kind="Text", optional=True))
        car_schema.relationships.append(
            RelationshipSchema(
                name="partner_car", peer="TestingCar", optional=True, cardinality=RelationshipCardinality.ONE
            )
        )
        return car_schema

    @pytest.fixture(scope="class")
    async def branch(self, client: InfrahubClient) -> BranchData:
        return await client.branch.create(branch_name="duplicated_schema")

    @pytest.fixture(scope="class")
    async def load_schema_on_branch(
        self, client: InfrahubClient, load_schema: None, car_schema_updated: NodeSchema, branch: BranchData
    ) -> None:
        schema_root = SchemaRoot(nodes=[car_schema_updated], version="1.0")
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=branch.name)
        assert len(response.errors) == 0, response.errors

    @pytest.fixture(scope="class")
    async def load_schema_on_main(
        self, client: InfrahubClient, load_schema: None, car_schema_updated: NodeSchema, default_branch: Branch
    ) -> None:
        schema_root = SchemaRoot(nodes=[car_schema_updated], version="1.0")
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=default_branch.name)
        assert len(response.errors) == 0, response.errors

    async def _load_data(self, client: InfrahubClient, branch_name: str) -> dict[str, InfrahubNode]:
        manufacturer = await client.create(
            branch=branch_name, kind="TestingManufacturer", name=f"car-maker-{branch_name}"
        )
        await manufacturer.save()
        person = await client.create(branch=branch_name, kind="TestingPerson", name=f"person-{branch_name}")
        await person.save()
        car_1 = await client.create(
            branch=branch_name,
            kind="TestingCar",
            name=f"car-1-{branch_name}",
            manufacturer=manufacturer,
            owner=person,
            color="blurple",
            smell="good",
        )
        await car_1.save()
        car_2 = await client.create(
            branch=branch_name,
            kind="TestingCar",
            name=f"car-2-{branch_name}",
            manufacturer=manufacturer,
            owner=person,
            color="deep-blurple",
            partner_car=car_1.id,
            smell="bad",
        )
        await car_2.save()
        return {
            "manufacturer": manufacturer,
            "person": person,
            "car_1": car_1,
            "car_2": car_2,
        }

    async def test_merge_fails_with_duplicates(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        load_schema_on_branch: None,
        load_schema_on_main: None,
        branch: BranchData,
    ) -> None:
        car_schema_main = await client.schema.get(kind="TestingCar", branch=default_branch.name, refresh=True)
        car_attributes_by_name_main = {attr.name: attr for attr in car_schema_main.attributes}
        smell_attr_main = car_attributes_by_name_main["smell"]
        car_relationships_by_name_main = {rel.name: rel for rel in car_schema_main.relationships}
        partner_car_rel_main = car_relationships_by_name_main["partner_car"]
        car_schema_branch = await client.schema.get(kind="TestingCar", branch=branch.name, refresh=True)
        car_attributes_by_name_branch = {attr.name: attr for attr in car_schema_branch.attributes}
        smell_attr_branch = car_attributes_by_name_branch["smell"]
        car_relationships_by_name_branch = {rel.name: rel for rel in car_schema_branch.relationships}
        partner_car_rel_branch = car_relationships_by_name_branch["partner_car"]

        for operation in [
            client.branch.merge(branch_name=branch.name),
            client.branch.rebase(branch_name=branch.name),
        ]:
            with pytest.raises(GraphQLError) as excinfo:
                await operation

            expected_error_messages = [
                f"(SchemaAttribute: {smell_attr_main.id}) is not compliant. The error relates to field name.value='smell'",
                f"(SchemaAttribute: {smell_attr_branch.id}) is not compliant. The error relates to field name.value='smell'",
                f"(SchemaAttribute: {smell_attr_main.id}) is not compliant. The error relates to field node.id='{car_schema_main.id}'",
                f"(SchemaAttribute: {smell_attr_branch.id}) is not compliant. The error relates to field node.id='{car_schema_main.id}'",
                f"(SchemaRelationship: {partner_car_rel_main.id}) is not compliant. The error relates to field name.value='partner_car'",
                f"(SchemaRelationship: {partner_car_rel_branch.id}) is not compliant. The error relates to field name.value='partner_car'",
                f"(SchemaRelationship: {partner_car_rel_main.id}) is not compliant. The error relates to field node.id='{car_schema_main.id}'",
                f"(SchemaRelationship: {partner_car_rel_branch.id}) is not compliant. The error relates to field node.id='{car_schema_main.id}'",
            ]
            for expected_err in expected_error_messages:
                assert expected_err in excinfo.value.errors[0]["message"]

    async def test_merge_succeeds_after_schema_duplicates_are_deleted(
        self, client: InfrahubClient, default_branch: Branch, branch: BranchData, car_schema_updated: NodeSchema
    ) -> None:
        car_schema_branch = await client.schema.get(kind="TestingCar", branch=branch.name, refresh=True)
        car_attributes_by_name_branch = {attr.name: attr for attr in car_schema_branch.attributes}
        smell_attr_branch = car_attributes_by_name_branch["smell"]
        car_relationships_by_name_branch = {rel.name: rel for rel in car_schema_branch.relationships}
        partner_car_rel_branch = car_relationships_by_name_branch["partner_car"]

        fixed_car_schema = car_schema_updated.duplicate()
        smell_attribute = fixed_car_schema.get_attribute("smell")
        smell_attribute.id = smell_attr_branch.id
        smell_attribute.state = HashableModelState.ABSENT
        partner_car_relationship = fixed_car_schema.get_relationship("partner_car")
        partner_car_relationship.id = partner_car_rel_branch.id
        partner_car_relationship.state = HashableModelState.ABSENT

        schema_root = SchemaRoot(nodes=[fixed_car_schema], version="1.0")
        response = await client.schema.load(schemas=[schema_root.model_dump()], branch=branch.name)
        assert len(response.errors) == 0, response.errors

        is_success = await client.branch.merge(branch_name=branch.name)
        assert is_success

        car_schema_branch = await client.schema.get(kind="TestingCar", branch=default_branch.name, refresh=True)
        car_attribute_names = {attr.name for attr in car_schema_branch.attributes}
        assert "smell" in car_attribute_names
        car_relationship_names = {rel.name for rel in car_schema_branch.relationships}
        assert "partner_car" in car_relationship_names

        loaded_nodes_map = await self._load_data(client, default_branch.name)
        cars = [loaded_nodes_map["car_1"], loaded_nodes_map["car_2"]]
        for car in cars:
            fresh_car = await client.get(kind="TestingCar", id=car.id)
            assert fresh_car.smell.value == car.smell.value
            await fresh_car.partner_car.fetch()
            partner_car = cars[0] if car.id == cars[1].id else cars[1]
            assert fresh_car.partner_car.id == partner_car.id

    async def test_load_schema_on_branch_alternate_user(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        load_schema: None,
        admin_account: CoreAccount,
        bot_account: CoreAccount,
    ) -> None:
        branch_name = "user_feature_branch"
        await client.branch.create(branch_name=branch_name)

        schema_root = SNOW_TICKET_SCHEMA.duplicate()
        schema_root.version = "1.0"

        response = await bot_client.schema.load(schemas=[schema_root.model_dump()], branch=branch_name)
        assert len(response.errors) == 0, response.errors

        async with db.start_session() as dbs:
            feature_branch = await Branch.get_by_name(db=dbs, name=branch_name)
        assert feature_branch.created_by == admin_account.id
        assert feature_branch.updated_by == bot_account.id
