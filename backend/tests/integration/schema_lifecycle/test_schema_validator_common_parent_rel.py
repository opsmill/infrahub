import copy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.schema.device import LAG_INTERFACE

from .shared import TestSchemaLifecycleBase


class TestSchemaLifecyclePeerParentUpdate(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_network(self) -> dict[str, Any]:
        DEVICE_SCHEMA.version = "1.0"
        return DEVICE_SCHEMA.model_dump()

    @pytest.fixture(scope="class")
    def schema_lag_interface(self) -> dict[str, Any]:
        lag_without_constraint = copy.deepcopy(LAG_INTERFACE)
        lag_without_constraint.relationships[0].common_parent = None
        return SchemaRoot(version="1.0", generics=[], nodes=[lag_without_constraint]).model_dump()

    @pytest.fixture(scope="class")
    def schema_constrained_lag_interface(self) -> dict[str, Any]:
        return SchemaRoot(version="1.0", generics=[], nodes=[LAG_INTERFACE]).model_dump()

    async def test_step_01_create_branch(self, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="test", sync_with_git=False)
        assert branch

    async def test_step_02_load_schema(self, client: InfrahubClient, schema_network: dict[str, Any]) -> None:
        response = await client.schema.load(schemas=[schema_network], branch="test")
        assert not response.errors

    async def test_step_03_add_lag_node_to_schema(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_lag_interface: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_lag_interface], branch="test")
        assert not response.errors

    async def test_step_04_create_devices(self, client: InfrahubClient) -> None:
        for name in ["device_1", "device_2"]:
            device = await client.create(
                branch="test", kind=TestKind.DEVICE, name=name, manufacturer="Foo", weight=10, airflow="Front to rear"
            )
            await device.save()

            for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
                interface = await client.create(
                    branch="test",
                    kind=TestKind.PHYSICAL_INTERFACE,
                    name=if_name,
                    phys_type="QSFP28 (100GE)",
                    device=device,
                )
                await interface.save()

    async def test_step05_create_lag_with_all_interfaces(self, client: InfrahubClient) -> None:
        device = await client.get(branch="test", kind=TestKind.DEVICE, name__value="device_1")
        await device.interfaces.fetch()
        lag = await client.create(
            branch="test", kind=TestKind.LAG_INTERFACE, name="ae0", device=device, members=device.interfaces.peer_ids
        )
        await lag.save()

    async def test_step06_set_constraint_to_lag(
        self, client: InfrahubClient, schema_constrained_lag_interface: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_constrained_lag_interface], branch="test")
        assert not response.errors

    async def test_step07_create_lag_with_relationship_add(self, client: InfrahubClient) -> None:
        device = await client.get(branch="test", kind=TestKind.DEVICE, name__value="device_2")
        await device.interfaces.fetch()
        lag = await client.create(
            branch="test",
            kind=TestKind.LAG_INTERFACE,
            name="ae0",
            device=device,
            members=[device.interfaces.peer_ids[0]],
        )
        await lag.save()

        query = """
        mutation {
            RelationshipAdd(
                data: {
                    id: "%s",
                    name: "members",
                    nodes: [ %s ]
                }
            ) {
                ok
            }
        }
        """ % (lag.id, ", ".join(f'{{id: "{i}"}}' for i in device.interfaces.peer_ids[1:]))

        response = await client.execute_graphql(query=query, branch_name="test", tracker="add-members-to-lag")
        assert response["RelationshipAdd"]["ok"]

        nodes = []
        for i in lag.members.peer_ids:
            nodes.append(await client.get(branch="test", kind=TestKind.PHYSICAL_INTERFACE, id=i))

        assert {n.device.id for n in nodes} == {device.id}

    async def test_step08_incorrectly_update_lag(self, client: InfrahubClient) -> None:
        device1 = await client.get(branch="test", kind=TestKind.DEVICE, name__value="device_1")
        device2 = await client.get(branch="test", kind=TestKind.DEVICE, name__value="device_2")
        await device2.interfaces.fetch()

        # Get LAG from device 1 and try to add interfaces from device 2 (this must fail)
        lag = await client.get(branch="test", kind=TestKind.LAG_INTERFACE, name__value="ae0", device__ids=[device1.id])

        query = """
        mutation {
            RelationshipAdd(
                data: {
                    id: "%s",
                    name: "members",
                    nodes: [ %s ]
                }
            ) {
                ok
            }
        }
        """ % (
            lag.id,
            ", ".join(
                f'{{id: "{i.id}"}}'
                for i in device2.interfaces.peers
                if i.get().get_kind() == TestKind.PHYSICAL_INTERFACE
            ),
        )

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query, branch_name="test", tracker="add-members-to-lag")

        assert "do not have the same parent" in exc.value.errors[0]["message"]

        await lag.members.fetch()
        nodes = []
        for i in lag.members.peer_ids:
            nodes.append(await client.get(branch="test", kind=TestKind.PHYSICAL_INTERFACE, id=i))

        assert {n.device.id for n in nodes} == {device1.id}

    async def test_final_validate(self, db: InfrahubDatabase):
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
