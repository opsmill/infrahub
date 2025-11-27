from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.relationship.peer import (
    RelationshipPeerParentChecker,
    RelationshipPeerParentValidatorQuery,
)
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.schema.device import DATACENTER_DEVICE, LAG_INTERFACE
from tests.helpers.schema.location import (
    DATACENTER_HIERARCHY,
    DATACENTER_RACK_WITH_CONSTRAINT,
    DATACENTER_SITE,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase


async def add_interfaces_to_device(db: InfrahubDatabase, branch: Branch, device: Node) -> list[Node]:
    interfaces: list[Node] = []
    for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
        interface = await Node.init(db=db, branch=branch, schema=TestKind.PHYSICAL_INTERFACE)
        await interface.new(db=db, name=if_name, phys_type="QSFP28 (100GE)", device=device)
        await interface.save(db=db)
        interfaces.append(interface)

    await device.interfaces.update(db=db, data=interfaces)
    await device.save(db=db)
    return interfaces


async def add_lag_to_device(
    db: InfrahubDatabase, branch: Branch, device: Node, name: str, members: Sequence[Node]
) -> Node:
    lag = await Node.init(db=db, branch=branch, schema=TestKind.LAG_INTERFACE)
    await lag.new(db=db, name=name, members=list(members), device=device)
    await lag.save(db=db)

    await device.interfaces.update(db=db, data=lag)
    await device.save(db=db)

    return lag


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    schema = copy.deepcopy(DEVICE_SCHEMA)
    schema.nodes.append(LAG_INTERFACE)
    schema.get(name=TestKind.DEVICE).generate_template = False
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def data_empty_lags(db: InfrahubDatabase, device_schema: SchemaRoot, default_branch: Branch) -> dict[str, Node]:
    d_1 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_1.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
    await d_1.save(db=db)
    d_1_lag = await add_lag_to_device(db=db, branch=default_branch, device=d_1, name="ae0", members=[])

    d_2 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_2.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
    await d_2.save(db=db)
    d_2_lag = await add_lag_to_device(db=db, branch=default_branch, device=d_2, name="ae0", members=[])

    return {"d_1": d_1, "d_2": d_2, "d_1_lag": d_1_lag, "d_2_lag": d_2_lag}


@pytest.fixture
async def data_invalid_lag(db: InfrahubDatabase, device_schema: SchemaRoot, default_branch: Branch) -> dict[str, Node]:
    d_1 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_1.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
    await d_1.save(db=db)
    d_1_interfaces = await add_interfaces_to_device(db=db, branch=default_branch, device=d_1)
    d_1_lag = await add_lag_to_device(db=db, branch=default_branch, device=d_1, name="ae0", members=d_1_interfaces)

    d_2 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_2.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
    await d_2.save(db=db)
    await add_interfaces_to_device(db=db, branch=default_branch, device=d_2)
    d_2_lag = await add_lag_to_device(db=db, branch=default_branch, device=d_2, name="ae0", members=d_1_interfaces)

    return {"d_1": d_1, "d_2": d_2, "d_1_lag": d_1_lag, "d_2_lag": d_2_lag}


@pytest.fixture
async def expected_invalid_lag_data_paths(
    db: InfrahubDatabase, default_branch: Branch, data_invalid_lag, branch: Branch
) -> set[DataPath]:
    branch_d2_lag = await NodeManager.get_one(db=db, branch=branch, id=data_invalid_lag["d_2_lag"].id)
    d2_lag_members = await branch_d2_lag.members.get_peers(db=db)
    return {
        DataPath(
            branch=default_branch.name,
            path_type=PathType.RELATIONSHIP_ONE,
            node_id=member.id,
            kind=member.get_kind(),
            field_name="device",
            peer_id=data_invalid_lag["d_1"].id,
        )
        for member in d2_lag_members.values()
    }


@pytest.fixture
async def hierarchy_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema with hierarchical Site -> Rack, Device structure with common_parent constraint."""
    schema = copy.deepcopy(DEVICE_SCHEMA)
    schema.generics.append(DATACENTER_HIERARCHY)
    schema.nodes.extend([DATACENTER_SITE, DATACENTER_RACK_WITH_CONSTRAINT, DATACENTER_DEVICE])
    # Disable template generation to avoid CoreObjectComponentTemplate dependency
    for node in schema.nodes:
        node.generate_template = False
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def hierarchy_data_empty_racks(
    db: InfrahubDatabase, hierarchy_schema: SchemaRoot, default_branch: Branch
) -> dict[str, Node]:
    """Create sites and racks without devices."""
    site_1 = await Node.init(db=db, schema=TestKind.DATACENTER_SITE, branch=default_branch)
    await site_1.new(db=db, name="site_1", location="Location 1")
    await site_1.save(db=db)

    site_2 = await Node.init(db=db, schema=TestKind.DATACENTER_SITE, branch=default_branch)
    await site_2.new(db=db, name="site_2", location="Location 2")
    await site_2.save(db=db)

    rack_1_1 = await Node.init(db=db, schema=TestKind.DATACENTER_RACK, branch=default_branch)
    await rack_1_1.new(db=db, name="rack_1_1", position=1, parent=site_1)
    await rack_1_1.save(db=db)

    rack_2_1 = await Node.init(db=db, schema=TestKind.DATACENTER_RACK, branch=default_branch)
    await rack_2_1.new(db=db, name="rack_2_1", position=1, parent=site_2)
    await rack_2_1.save(db=db)

    return {"site_1": site_1, "site_2": site_2, "rack_1_1": rack_1_1, "rack_2_1": rack_2_1}


@pytest.fixture
async def hierarchy_data_invalid_rack(
    db: InfrahubDatabase, hierarchy_schema: SchemaRoot, default_branch: Branch
) -> dict[str, Node]:
    """Create racks with devices violating common_parent constraint."""
    site_1 = await Node.init(db=db, schema=TestKind.DATACENTER_SITE, branch=default_branch)
    await site_1.new(db=db, name="site_1", location="Location 1")
    await site_1.save(db=db)

    site_2 = await Node.init(db=db, schema=TestKind.DATACENTER_SITE, branch=default_branch)
    await site_2.new(db=db, name="site_2", location="Location 2")
    await site_2.save(db=db)

    # Create devices for each site
    device_1_1 = await Node.init(db=db, schema=TestKind.DATACENTER_DEVICE, branch=default_branch)
    await device_1_1.new(db=db, name="device_1_1", device_type="Server", parent=site_1)
    await device_1_1.save(db=db)

    device_1_2 = await Node.init(db=db, schema=TestKind.DATACENTER_DEVICE, branch=default_branch)
    await device_1_2.new(db=db, name="device_1_2", device_type="Server", parent=site_1)
    await device_1_2.save(db=db)

    device_2_1 = await Node.init(db=db, schema=TestKind.DATACENTER_DEVICE, branch=default_branch)
    await device_2_1.new(db=db, name="device_2_1", device_type="Server", parent=site_2)
    await device_2_1.save(db=db)

    # Create rack in site_1 with valid devices
    rack_1_1 = await Node.init(db=db, schema=TestKind.DATACENTER_RACK, branch=default_branch)
    await rack_1_1.new(db=db, name="rack_1_1", position=1, parent=site_1, devices=[device_1_1, device_1_2])
    await rack_1_1.save(db=db)

    # Create rack in site_2 with devices from site_1 (INVALID)
    rack_2_1 = await Node.init(db=db, schema=TestKind.DATACENTER_RACK, branch=default_branch)
    await rack_2_1.new(db=db, name="rack_2_1", position=1, parent=site_2, devices=[device_1_1, device_1_2])
    await rack_2_1.save(db=db)

    return {
        "site_1": site_1,
        "site_2": site_2,
        "rack_1_1": rack_1_1,
        "rack_2_1": rack_2_1,
        "device_1_1": device_1_1,
        "device_1_2": device_1_2,
        "device_2_1": device_2_1,
    }


@pytest.fixture
async def expected_hierarchy_invalid_data_paths(
    db: InfrahubDatabase, default_branch: Branch, hierarchy_data_invalid_rack, branch: Branch
) -> set[DataPath]:
    """Expected violation paths for devices in rack_2_1 with wrong parent."""
    branch_rack_2_1 = await NodeManager.get_one(db=db, branch=branch, id=hierarchy_data_invalid_rack["rack_2_1"].id)
    rack_devices = await branch_rack_2_1.devices.get_peers(db=db)
    return {
        DataPath(
            branch=default_branch.name,
            path_type=PathType.RELATIONSHIP_ONE,
            node_id=device.id,
            kind=device.get_kind(),
            field_name="parent",
            peer_id=hierarchy_data_invalid_rack["site_1"].id,
        )
        for device in rack_devices.values()
    }

async def test_query_no_relationships(db: InfrahubDatabase, branch: Branch, data_empty_lags: dict[str, Any]):
    lag_schema = registry.schema.get(name=TestKind.LAG_INTERFACE)
    interface_schema = registry.schema.get(TestKind.PHYSICAL_INTERFACE)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=lag_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=lag_schema.kind, field_name="members"
        ),
        relationship=lag_schema.get_relationship(name="members"),
        parent_relationship=lag_schema.get_relationship(name="device"),
        peer_parent_relationship=interface_schema.get_relationship(name="device"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_query_invalid_lag(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_invalid_lag: dict[str, Node],
    expected_invalid_lag_data_paths: set[DataPath],
    branch: Branch,
) -> None:
    lag_schema = registry.schema.get(name=TestKind.LAG_INTERFACE)
    interface_schema = registry.schema.get(TestKind.PHYSICAL_INTERFACE)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=lag_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=lag_schema.kind, field_name="members"
        ),
        relationship=lag_schema.get_relationship(name="members"),
        parent_relationship=lag_schema.get_relationship(name="device"),
        peer_parent_relationship=interface_schema.get_relationship(name="device"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert set(all_paths) == expected_invalid_lag_data_paths


async def test_query_deleted_lag_members(
    db: InfrahubDatabase, data_invalid_lag: dict[str, Node], branch: Branch
) -> None:
    lag_schema = registry.schema.get(name=TestKind.LAG_INTERFACE)
    interface_schema = registry.schema.get(TestKind.PHYSICAL_INTERFACE)

    for lag in [data_invalid_lag["d_1_lag"], data_invalid_lag["d_2_lag"]]:
        branch_lag = await NodeManager.get_one(db=db, branch=branch, id=lag.id)
        await branch_lag.members.update(db=db, data=None)
        await branch_lag.members.save(db=db)

        assert not await branch_lag.members.get_peers(db=db)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=lag_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=lag_schema.kind, field_name="members"
        ),
        relationship=lag_schema.get_relationship(name="members"),
        parent_relationship=lag_schema.get_relationship(name="device"),
        peer_parent_relationship=interface_schema.get_relationship(name="device"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_validator(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_invalid_lag: dict[str, Node],
    expected_invalid_lag_data_paths: set[DataPath],
    branch: Branch,
) -> None:
    lag_schema = registry.schema.get(name=TestKind.LAG_INTERFACE)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="relationship.common_parent.update",
        node_schema=lag_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=lag_schema.kind, field_name="members"
        ),
        schema_branch=registry.schema.get_schema_branch(default_branch.name),
    )

    constraint_checker = RelationshipPeerParentChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_paths = grouped_data_paths[0].get_all_data_paths()
    assert all_paths


async def test_hierarchy_query_no_relationships(
    db: InfrahubDatabase, branch: Branch, hierarchy_data_empty_racks: dict[str, Any]
):
    """Query should return no violations when racks have no devices."""
    rack_schema = registry.schema.get(name=TestKind.DATACENTER_RACK)
    device_schema = registry.schema.get(name=TestKind.DATACENTER_DEVICE)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=rack_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=rack_schema.kind, field_name="devices"
        ),
        relationship=rack_schema.get_relationship(name="devices"),
        parent_relationship=rack_schema.get_relationship(name="parent"),
        peer_parent_relationship=device_schema.get_relationship(name="parent"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_hierarchy_query_invalid_rack(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchy_data_invalid_rack: dict[str, Node],
    expected_hierarchy_invalid_data_paths: set[DataPath],
    branch: Branch,
):
    """Query should detect devices with different parent than their rack."""
    rack_schema = registry.schema.get(name=TestKind.DATACENTER_RACK)
    device_schema = registry.schema.get(name=TestKind.DATACENTER_DEVICE)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=rack_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=rack_schema.kind, field_name="devices"
        ),
        relationship=rack_schema.get_relationship(name="devices"),
        parent_relationship=rack_schema.get_relationship(name="parent"),
        peer_parent_relationship=device_schema.get_relationship(name="parent"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert set(all_paths) == expected_hierarchy_invalid_data_paths


async def test_hierarchy_query_deleted_rack_devices(
    db: InfrahubDatabase, hierarchy_data_invalid_rack: dict[str, Node], branch: Branch
):
    """Query should return no violations after removing all devices from racks."""
    rack_schema = registry.schema.get(name=TestKind.DATACENTER_RACK)
    device_schema = registry.schema.get(name=TestKind.DATACENTER_DEVICE)

    for rack in [hierarchy_data_invalid_rack["rack_1_1"], hierarchy_data_invalid_rack["rack_2_1"]]:
        branch_rack = await NodeManager.get_one(db=db, branch=branch, id=rack.id)
        await branch_rack.devices.update(db=db, data=None)
        await branch_rack.devices.save(db=db)

        assert not await branch_rack.devices.get_peers(db=db)

    query = await RelationshipPeerParentValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=rack_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=rack_schema.kind, field_name="devices"
        ),
        relationship=rack_schema.get_relationship(name="devices"),
        parent_relationship=rack_schema.get_relationship(name="parent"),
        peer_parent_relationship=device_schema.get_relationship(name="parent"),
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0


async def test_hierarchy_validator(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchy_data_invalid_rack: dict[str, Node],
    expected_hierarchy_invalid_data_paths: set[DataPath],
    branch: Branch,
):
    """Full validator test for hierarchical common_parent constraint."""
    rack_schema = registry.schema.get(name=TestKind.DATACENTER_RACK)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="relationship.common_parent.update",
        node_schema=rack_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=rack_schema.kind, field_name="devices"
        ),
        schema_branch=registry.schema.get_schema_branch(default_branch.name),
    )

    constraint_checker = RelationshipPeerParentChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_paths = grouped_data_paths[0].get_all_data_paths()
    assert all_paths
