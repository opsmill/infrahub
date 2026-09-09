from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
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
from tests.helpers.schema.device import LAG_INTERFACE

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


def register_device_schema(branch: Branch) -> SchemaRoot:
    schema = copy.deepcopy(DEVICE_SCHEMA)
    schema.nodes.append(LAG_INTERFACE)
    schema.get(name=TestKind.DEVICE).generate_template = False
    registry.schema.register_schema(schema=schema, branch=branch.name)
    return schema


async def build_data_empty_lags(db: InfrahubDatabase, branch: Branch) -> dict[str, Node]:
    d_1 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_1.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
    await d_1.save(db=db)
    d_1_lag = await add_lag_to_device(db=db, branch=branch, device=d_1, name="ae0", members=[])

    d_2 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_2.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
    await d_2.save(db=db)
    d_2_lag = await add_lag_to_device(db=db, branch=branch, device=d_2, name="ae0", members=[])

    return {"d_1": d_1, "d_2": d_2, "d_1_lag": d_1_lag, "d_2_lag": d_2_lag}


async def build_data_invalid_lag(db: InfrahubDatabase, branch: Branch) -> dict[str, Node]:
    d_1 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_1.new(db=db, name="Foo", manufacturer="Foo Inc.", weight=10, airflow="Front to rear")
    await d_1.save(db=db)
    d_1_interfaces = await add_interfaces_to_device(db=db, branch=branch, device=d_1)
    d_1_lag = await add_lag_to_device(db=db, branch=branch, device=d_1, name="ae0", members=d_1_interfaces)

    d_2 = await Node.init(db=db, schema=TestKind.DEVICE)
    await d_2.new(db=db, name="Bar", manufacturer="Bar Inc.", weight=10, airflow="Front to rear")
    await d_2.save(db=db)
    await add_interfaces_to_device(db=db, branch=branch, device=d_2)
    d_2_lag = await add_lag_to_device(db=db, branch=branch, device=d_2, name="ae0", members=d_1_interfaces)

    return {"d_1": d_1, "d_2": d_2, "d_1_lag": d_1_lag, "d_2_lag": d_2_lag}


def build_validator_query_kwargs(branch: Branch) -> dict[str, Any]:
    lag_schema = registry.schema.get(name=TestKind.LAG_INTERFACE)
    interface_schema = registry.schema.get(TestKind.PHYSICAL_INTERFACE)
    return {
        "branch": branch,
        "node_schema": lag_schema,
        "schema_path": SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=lag_schema.kind, field_name="members"
        ),
        "relationship": lag_schema.get_relationship(name="members"),
        "parent_relationship": lag_schema.get_relationship(name="device"),
        "peer_parent_relationship": interface_schema.get_relationship(name="device"),
    }


class TestQueryWithEmptyLags:
    """Read-only tests sharing one dataset built once for the class."""

    @pytest.fixture(scope="class")
    async def data_empty_lags(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> dict[str, Node]:
        register_device_schema(branch=default_branch_scope_class)
        return await build_data_empty_lags(db=db, branch=default_branch_scope_class)

    @pytest.fixture(scope="class", params=["main", "branch2"])
    async def branch(
        self,
        request: pytest.FixtureRequest,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        data_empty_lags: dict[str, Node],
    ) -> Branch:
        if request.param == "main":
            return default_branch_scope_class

        return await create_branch(branch_name=str(request.param), db=db)

    async def test_query_no_relationships(
        self, db: InfrahubDatabase, branch: Branch, data_empty_lags: dict[str, Any]
    ) -> None:
        query = await RelationshipPeerParentValidatorQuery.init(db=db, **build_validator_query_kwargs(branch=branch))
        await query.execute(db=db)

        grouped_paths = await query.get_paths()
        all_paths = grouped_paths.get_all_data_paths()
        assert len(all_paths) == 0


class TestQueryWithInvalidLag:
    """Read-only tests sharing one dataset built once for the class."""

    @pytest.fixture(scope="class")
    async def data_invalid_lag(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> dict[str, Node]:
        register_device_schema(branch=default_branch_scope_class)
        return await build_data_invalid_lag(db=db, branch=default_branch_scope_class)

    @pytest.fixture(scope="class", params=["main", "branch2"])
    async def branch(
        self,
        request: pytest.FixtureRequest,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        data_invalid_lag: dict[str, Node],
    ) -> Branch:
        if request.param == "main":
            return default_branch_scope_class

        return await create_branch(branch_name=str(request.param), db=db)

    @pytest.fixture(scope="class")
    async def expected_invalid_lag_data_paths(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        data_invalid_lag: dict[str, Node],
        branch: Branch,
    ) -> set[DataPath]:
        branch_d2_lag = await NodeManager.get_one(db=db, branch=branch, id=data_invalid_lag["d_2_lag"].id)
        d2_lag_members = await branch_d2_lag.members.get_peers(db=db)
        return {
            DataPath(
                branch=default_branch_scope_class.name,
                path_type=PathType.RELATIONSHIP_ONE,
                node_id=member.id,
                kind=member.get_kind(),
                field_name="device",
                peer_id=data_invalid_lag["d_1"].id,
            )
            for member in d2_lag_members.values()
        }

    async def test_query_invalid_lag(
        self,
        db: InfrahubDatabase,
        data_invalid_lag: dict[str, Node],
        expected_invalid_lag_data_paths: set[DataPath],
        branch: Branch,
    ) -> None:
        query = await RelationshipPeerParentValidatorQuery.init(db=db, **build_validator_query_kwargs(branch=branch))
        await query.execute(db=db)

        grouped_paths = await query.get_paths()
        all_paths = grouped_paths.get_all_data_paths()
        assert set(all_paths) == expected_invalid_lag_data_paths

    async def test_validator(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
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
            schema_branch=registry.schema.get_schema_branch(default_branch_scope_class.name),
        )

        constraint_checker = RelationshipPeerParentChecker(db=db, branch=branch)
        grouped_data_paths = await constraint_checker.check(request)

        assert len(grouped_data_paths) == 1
        all_paths = grouped_data_paths[0].get_all_data_paths()
        assert all_paths


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    return register_device_schema(branch=default_branch)


@pytest.fixture
async def data_invalid_lag(db: InfrahubDatabase, device_schema: SchemaRoot, default_branch: Branch) -> dict[str, Node]:
    return await build_data_invalid_lag(db=db, branch=default_branch)


async def test_query_deleted_lag_members(
    db: InfrahubDatabase, data_invalid_lag: dict[str, Node], branch: Branch
) -> None:
    # Mutates the shared-looking dataset, so it keeps its own function-scoped copy.
    for lag in [data_invalid_lag["d_1_lag"], data_invalid_lag["d_2_lag"]]:
        branch_lag = await NodeManager.get_one(db=db, branch=branch, id=lag.id)
        await branch_lag.members.update(db=db, data=None)
        await branch_lag.members.save(db=db)

        assert not await branch_lag.members.get_peers(db=db)

    query = await RelationshipPeerParentValidatorQuery.init(db=db, **build_validator_query_kwargs(branch=branch))
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_all_data_paths()
    assert len(all_paths) == 0
