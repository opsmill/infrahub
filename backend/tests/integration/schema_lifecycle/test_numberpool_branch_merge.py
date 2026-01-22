from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


DEVICE_KIND = "TestingDevice"


class TestNumberPoolBranchMerge(TestInfrahubApp):
    """Test creating schema with NumberPool on default and branch, then merging."""

    @pytest.fixture(scope="class")
    def schema_with_numberpool(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Testing",
                    "include_in_menu": True,
                    "label": "Device",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {
                            "name": "port_number",
                            "kind": "NumberPool",
                            "optional": False,
                            "read_only": True,
                            "parameters": {"start_range": 1, "end_range": 65535},
                        },
                    ],
                }
            ],
        }

    @pytest.fixture(scope="class")
    async def persist_core_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initialize_registry: None,
    ) -> None:
        """Persist the core schema to the database so merge workflows can find it."""
        branch_schema = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(
            schema=branch_schema.duplicate(), db=db, branch=default_branch.name, update_db=True
        )

    @pytest.fixture(scope="class")
    async def setup_branch(
        self,
        db: InfrahubDatabase,
        persist_core_schema: None,
    ) -> Branch:
        # Create a branch before loading the schema
        branch = await create_branch(db=db, branch_name="numberpool-test-branch")
        return branch

    @pytest.fixture(scope="class")
    async def load_schema_on_default(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        schema_with_numberpool: dict[str, Any],
        setup_branch: Branch,
    ) -> None:
        # Load schema on default branch using InfrahubClient
        response = await client.schema.load(schemas=[schema_with_numberpool], branch=default_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def create_device_on_default(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_schema_on_default: None,
    ) -> Node:
        # Create a TestingDevice instance on the default branch
        device = await Node.init(schema=DEVICE_KIND, db=db, branch=default_branch)
        await device.new(db=db, name="device-default")
        await device.save(db=db)
        return device

    @pytest.fixture(scope="class")
    async def load_schema_on_branch(
        self,
        client: InfrahubClient,
        setup_branch: Branch,
        create_device_on_default: Node,
        schema_with_numberpool: dict[str, Any],
    ) -> None:
        # Load the same schema on the branch using InfrahubClient
        response = await client.schema.load(schemas=[schema_with_numberpool], branch=setup_branch.name)
        assert not response.errors

    @pytest.fixture(scope="class")
    async def create_device_on_branch(
        self,
        db: InfrahubDatabase,
        setup_branch: Branch,
        load_schema_on_branch: None,
    ) -> Node:
        # Create a TestingDevice instance on the branch
        device = await Node.init(schema=DEVICE_KIND, db=db, branch=setup_branch)
        await device.new(db=db, name="device-branch")
        await device.save(db=db)
        return device

    async def test_devices_created(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        setup_branch: Branch,
        create_device_on_default: Node,
        create_device_on_branch: Node,
    ) -> None:
        # Verify devices exist on their respective branches
        default_devices = await registry.manager.query(db=db, schema=DEVICE_KIND, branch=default_branch)
        assert len(default_devices) == 1
        assert default_devices[0].name.value == "device-default"

        # Branch only sees the device created on it (device on default was created after branch)
        branch_devices = await registry.manager.query(db=db, schema=DEVICE_KIND, branch=setup_branch)
        assert len(branch_devices) == 1
        assert branch_devices[0].name.value == "device-branch"

    async def test_merge_branch(
        self,
        client: InfrahubClient,
        setup_branch: Branch,
        create_device_on_branch: Node,
    ) -> None:
        # Merge the branch back to default
        merged_branch = await client.branch.merge(branch_name=setup_branch.name)
        assert merged_branch is not None
