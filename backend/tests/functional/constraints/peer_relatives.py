from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA, load_schema
from tests.helpers.schema.device import LAG_INTERFACE
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestPeerRelativesConstraint(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def schema(self, default_branch: Branch, register_internal_schema: SchemaBranch) -> SchemaRoot:
        schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
        schema_with_lag.nodes[0].generate_template = False

        lag_node_schema = copy.deepcopy(LAG_INTERFACE)
        lag_node_schema.relationships[0].common_parent = None
        lag_node_schema.relationships[0].common_relatives = ["device"]
        schema_with_lag.nodes.append(lag_node_schema)

        return schema_with_lag

    @pytest.fixture(scope="class")
    async def data(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        default_branch: Branch,
        schema: SchemaRoot,
    ) -> dict[str, Node]:
        await load_schema(db, schema=schema, update_db=True)

        device_1 = await Node.init(db=db, schema=TestKind.DEVICE)
        await device_1.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")

        interfaces_1: list[Node] = []
        interfaces_1_ids: list[str] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device_1)
            await interface.save(db=db)
            interfaces_1.append(interface)
            interfaces_1_ids.append(interface.id)

        await device_1.interfaces.update(db=db, data=interfaces_1)  # type: ignore[attr-defined]
        await device_1.save(db=db)

        device_2 = await Node.init(db=db, schema=TestKind.DEVICE)
        await device_2.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")

        interfaces_2: list[Node] = []
        interfaces_2_ids: list[str] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device_2)
            await interface.save(db=db)
            interfaces_2.append(interface)
            interfaces_2_ids.append(interface.id)

        await device_2.interfaces.update(db=db, data=interfaces_2)  # type: ignore[attr-defined]
        await device_2.save(db=db)

        return {"device_1": device_1, "device_2": device_2}

    async def test_create_lag_main(
        self, db: InfrahubDatabase, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        device = await client.get(kind=TestKind.DEVICE, id=data["device_1"].id, branch=default_branch.name)
        await device.interfaces.fetch()

        lag = await client.create(
            kind=TestKind.LAG_INTERFACE,
            name="ae0",
            device=device,
            members=[i.peer for i in device.interfaces],  # type: ignore[attr-defined]
            branch=default_branch.name,
        )
        await lag.save()

        assert len(lag.members.peers) == 4
        assert sorted(lag.members.peer_ids) == sorted([i.id for i in device.interfaces])

    async def test_create_incorrect_lag_main(
        self, db: InfrahubDatabase, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        device_1 = await client.get(kind=TestKind.DEVICE, id=data["device_1"].id, branch=default_branch.name)
        await device_1.interfaces.fetch()
        device_2 = await client.get(kind=TestKind.DEVICE, id=data["device_2"].id, branch=default_branch.name)
        await device_2.interfaces.fetch()

        lag = await client.create(
            kind=TestKind.LAG_INTERFACE,
            name="ae1",
            device=device_1,
            members=[i.peer for i in list(device_1.interfaces)[:-1] + list(device_2.interfaces)],  # type: ignore[attr-defined]
            branch=default_branch.name,
        )

        with pytest.raises(GraphQLError) as exc:
            await lag.save()
        assert (
            "must have the same set of peers for their 'TestingPhysicalInterface.device' relationship"
            in exc.value.errors[0]["message"]
        )

    async def test_create_lag_branch(
        self, db: InfrahubDatabase, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        branch = await client.branch.create(branch_name="test-lag")

        device = await client.get(kind=TestKind.DEVICE, id=data["device_2"].id, branch=branch.name)
        await device.interfaces.fetch()

        lag = await client.create(
            kind=TestKind.LAG_INTERFACE,
            name="ae0",
            device=device,
            members=[i.peer for i in device.interfaces],  # type: ignore[attr-defined]
            branch=branch.name,
        )
        await lag.save()

        assert len(lag.members.peers) == 4
        assert sorted(lag.members.peer_ids) == sorted([i.id for i in device.interfaces])

    async def test_create_incorrect_lag_branch(
        self, db: InfrahubDatabase, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        branch = await client.branch.create(branch_name="test-lag-incorrect")

        device_1 = await client.get(kind=TestKind.DEVICE, id=data["device_1"].id, branch=branch.name)
        await device_1.interfaces.fetch()
        device_2 = await client.get(kind=TestKind.DEVICE, id=data["device_2"].id, branch=branch.name)
        await device_2.interfaces.fetch()

        lag = await client.create(
            kind=TestKind.LAG_INTERFACE,
            name="ae1",
            device=device_2,
            members=[i.peer for i in list(device_1.interfaces)[:-1] + list(device_2.interfaces)[:-1]],  # type: ignore[attr-defined]
            branch=branch.name,
        )

        with pytest.raises(GraphQLError) as exc:
            await lag.save()
        assert (
            "must have the same set of peers for their 'TestingPhysicalInterface.device' relationship"
            in exc.value.errors[0]["message"]
        )
