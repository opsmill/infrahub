import copy

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.relationship.constraints.peer_parent import RelationshipPeerParentConstraint
from infrahub.core.relationship.constraints.peer_relatives import RelationshipPeerRelativesConstraint
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.schema.device import LAG_INTERFACE
from tests.helpers.test_app import TestInfrahubApp


class TestRelationshipPeerParentConstraint(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def schema(self, default_branch: Branch, register_internal_schema: SchemaBranch) -> None:
        schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
        schema_with_lag.nodes[0].generate_template = False
        schema_with_lag.nodes.append(LAG_INTERFACE)
        return registry.schema.register_schema(schema=schema_with_lag, branch=registry.default_branch)

    @pytest.fixture
    async def device_1(self, db: InfrahubDatabase, schema) -> Node:
        device = await Node.init(db=db, schema=TestKind.DEVICE)
        await device.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
        await device.save(db=db)

        interfaces: list[Node] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device)
            await interface.save(db=db)
            interfaces.append(interface)

        await device.interfaces.update(db=db, data=interfaces)

        return device

    @pytest.fixture
    async def device_2(self, db: InfrahubDatabase, schema) -> Node:
        device = await Node.init(db=db, schema=TestKind.DEVICE)
        await device.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
        await device.save(db=db)

        interfaces: list[Node] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device)
            await interface.save(db=db)
            interfaces.append(interface)

        await device.interfaces.update(db=db, data=interfaces)

        return device

    async def test_same_parent(self, db: InfrahubDatabase, device_1: Node) -> None:
        lag_schema = registry.schema.get_node_schema(name=TestKind.LAG_INTERFACE, duplicate=False)

        constraint = RelationshipPeerParentConstraint(db=db)

        interfaces = await device_1.interfaces.get_peers(db=db)

        lag = await Node.init(db=db, schema=TestKind.LAG_INTERFACE)
        await lag.new(db=db, name="ae0", device=device_1, members=list(interfaces.values()))
        await lag.save(db=db)

        await constraint.check(relm=lag.members, node_schema=lag_schema, node=lag)

    async def test_different_parent(self, db: InfrahubDatabase, device_1: Node, device_2: Node) -> None:
        lag_schema = registry.schema.get_node_schema(name=TestKind.LAG_INTERFACE, duplicate=False)

        constraint = RelationshipPeerParentConstraint(db=db)

        interfaces_1 = await device_1.interfaces.get_peers(db=db)
        interfaces_2 = await device_2.interfaces.get_peers(db=db)
        interfaces = list(interfaces_1.values()) + list(interfaces_2.values())

        lag = await Node.init(db=db, schema=TestKind.LAG_INTERFACE)
        await lag.new(db=db, name="ae0", device=device_1, members=interfaces)
        await lag.save(db=db)

        with pytest.raises(ValidationError, match=r"must have the same parent"):
            await constraint.check(relm=lag.members, node_schema=lag_schema, node=lag)


class TestRelationshipPeerRelativesConstraint(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def schema(self, default_branch: Branch, register_internal_schema: SchemaBranch) -> None:
        lag = copy.deepcopy(LAG_INTERFACE)
        lag.relationships[0].common_parent = None
        lag.relationships[0].common_relatives = ["device"]

        schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
        schema_with_lag.nodes[0].generate_template = False
        schema_with_lag.nodes.append(lag)
        return registry.schema.register_schema(schema=schema_with_lag, branch=registry.default_branch)

    @pytest.fixture
    async def device_1(self, db: InfrahubDatabase, schema) -> Node:
        device = await Node.init(db=db, schema=TestKind.DEVICE)
        await device.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
        await device.save(db=db)

        interfaces: list[Node] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device)
            await interface.save(db=db)
            interfaces.append(interface)

        await device.interfaces.update(db=db, data=interfaces)

        return device

    @pytest.fixture
    async def device_2(self, db: InfrahubDatabase, schema) -> Node:
        device = await Node.init(db=db, schema=TestKind.DEVICE)
        await device.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
        await device.save(db=db)

        interfaces: list[Node] = []
        for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
            interface = await Node.init(db=db, schema=TestKind.PHYSICAL_INTERFACE)
            await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device)
            await interface.save(db=db)
            interfaces.append(interface)

        await device.interfaces.update(db=db, data=interfaces)

        return device

    async def test_common_relatives_allowed(self, db: InfrahubDatabase, device_1: Node) -> None:
        lag_schema = registry.schema.get_node_schema(name=TestKind.LAG_INTERFACE, duplicate=False)

        constraint = RelationshipPeerRelativesConstraint(db=db)

        interfaces = await device_1.interfaces.get_peers(db=db)

        lag = await Node.init(db=db, schema=TestKind.LAG_INTERFACE)
        await lag.new(db=db, name="ae0", device=device_1, members=list(interfaces.values()))
        await lag.save(db=db)

        await constraint.check(relm=lag.members, node_schema=lag_schema, node=lag)

    async def test_common_relatives_disallowed(self, db: InfrahubDatabase, device_1: Node, device_2: Node) -> None:
        lag_schema = registry.schema.get_node_schema(name=TestKind.LAG_INTERFACE, duplicate=False)

        constraint = RelationshipPeerRelativesConstraint(db=db)

        interfaces_1 = await device_1.interfaces.get_peers(db=db)
        interfaces_2 = await device_2.interfaces.get_peers(db=db)
        interfaces = list(interfaces_1.values()) + list(interfaces_2.values())

        lag = await Node.init(db=db, schema=TestKind.LAG_INTERFACE)
        await lag.new(db=db, name="ae0", device=device_1, members=interfaces)
        await lag.save(db=db)

        with pytest.raises(
            ValidationError,
            match=r"must have the same set of peers for their 'TestingPhysicalInterface.device' relationship",
        ):
            await constraint.check(relm=lag.members, node_schema=lag_schema, node=lag)
