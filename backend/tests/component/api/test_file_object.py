from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from tests.adapters.storage import DummyObjectStorage
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import FILE_CONTRACT
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient


class TestFileObjectDownload(TestInfrahubApp):
    """Tests for FileObject REST API download endpoint."""

    @staticmethod
    def get_download_url(storage_id: str) -> str:
        return f"/api/storage/{InfrahubKind.FILEOBJECT}/{storage_id}"

    @pytest.fixture(scope="class")
    def admin_headers(self, api_admin_token: str) -> dict[str, str]:
        return {"X-INFRAHUB-KEY": api_admin_token}

    @pytest.fixture(scope="class")
    async def no_permission_headers(self, db: InfrahubDatabase, file_contract_schema: None) -> dict[str, str]:
        """Create an account with no group membership (no permissions)."""
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="no-permission-user", password="password123")
        await account.save(db=db)

        token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
        await token.new(db=db, token="no-permission-token", account=account)
        await token.save(db=db)

        return {"X-INFRAHUB-KEY": token.token.value}

    @pytest.fixture(scope="class")
    async def view_permission_headers(self, db: InfrahubDatabase, file_contract_schema: None) -> dict[str, str]:
        """Create an account with VIEW permission only."""
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="view-permission-user", password="password123")
        await account.save(db=db)

        await define_permissions(
            account=account,
            db=db,
            object_permissions=[
                ObjectPermission(
                    namespace="*",
                    name="*",
                    action=PermissionAction.VIEW.value,
                    decision=PermissionDecision.ALLOW_ALL.value,
                ),
            ],
        )

        token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
        await token.new(db=db, token="view-permission-token", account=account)
        await token.save(db=db)

        return {"X-INFRAHUB-KEY": token.token.value}

    @pytest.fixture(scope="class")
    def dummy_storage(self) -> Generator[DummyObjectStorage, None, None]:
        storage = DummyObjectStorage()
        original_storage = registry._storage
        registry._storage = storage
        yield storage
        registry._storage = original_storage

    @pytest.fixture(scope="class")
    async def file_contract_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_schema: None, initialize_registry: None
    ) -> None:
        schema_root = SchemaRoot(nodes=[FILE_CONTRACT])
        registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def file_object_node(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> Node:
        """Create a FileObject node with stored content."""
        file_content = b"test file content for download"
        storage_id = "test-storage-id-123"
        checksum = hashlib.sha1(file_content, usedforsecurity=False).hexdigest()

        dummy_storage.store(identifier=storage_id, content=io.BytesIO(file_content))

        node = await Node.init(db=db, schema="TestingFileContract")
        await node.new(
            db=db,
            file_name="test-document.txt",
            file_size=len(file_content),
            file_type="text/plain",
            checksum=checksum,
            storage_id=storage_id,
            description="Test file for download",
        )
        await node.save(db=db)
        return node

    @pytest.fixture(scope="class")
    async def binary_file_object_node(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> Node:
        """Create a FileObject node with binary content."""
        # PNG header + some binary data
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        storage_id = "test-binary-storage-id-456"
        checksum = hashlib.sha1(file_content, usedforsecurity=False).hexdigest()

        dummy_storage.store(identifier=storage_id, content=io.BytesIO(file_content))

        node = await Node.init(db=db, schema="TestingFileContract")
        await node.new(
            db=db,
            file_name="test-image.png",
            file_size=len(file_content),
            file_type="image/png",
            checksum=checksum,
            storage_id=storage_id,
            description="Binary test file",
        )
        await node.save(db=db)
        return node

    async def test_download_file_returns_correct_content(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        file_object_node: Node,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that download endpoint returns the exact file content."""
        storage_id = file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=admin_headers)

        assert response.status_code == 200
        assert response.content == dummy_storage._files[storage_id]

    async def test_download_binary_file(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        binary_file_object_node: Node,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that binary files are returned correctly without encoding issues."""
        storage_id = binary_file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=admin_headers)

        assert response.status_code == 200
        assert response.content == dummy_storage._files[storage_id]
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    async def test_download_returns_correct_content_type(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        file_object_node: Node,
    ) -> None:
        """Test that response has the correct Content-Type from the FileObject node."""
        storage_id = file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=admin_headers)

        assert response.status_code == 200
        assert response.headers["content-type"] == f"{file_object_node.file_type.value}; charset=utf-8"

    async def test_download_returns_content_disposition_header(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        file_object_node: Node,
    ) -> None:
        """Test that response has Content-Disposition header with the filename."""
        storage_id = file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=admin_headers)

        assert response.status_code == 200
        assert "content-disposition" in response.headers
        content_disposition = response.headers["content-disposition"]
        assert "test-document.txt" in content_disposition
        assert content_disposition.startswith("attachment;")

    async def test_download_nonexistent_file_returns_404(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        file_contract_schema: None,
    ) -> None:
        """Test that downloading a nonexistent file returns 404."""
        response = await test_client.get(
            self.get_download_url(storage_id="nonexistent-storage-id"), headers=admin_headers
        )

        assert response.status_code == 404

    async def test_download_without_view_permission_returns_403(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        no_permission_headers: dict[str, str],
        file_object_node: Node,
    ) -> None:
        """Test that users without VIEW permission cannot download files."""
        storage_id = file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=no_permission_headers)

        assert response.status_code == 403

    async def test_download_with_view_permission_succeeds(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        view_permission_headers: dict[str, str],
        file_object_node: Node,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that users with VIEW permission can download files."""
        storage_id = file_object_node.storage_id.value
        response = await test_client.get(self.get_download_url(storage_id=storage_id), headers=view_permission_headers)

        assert response.status_code == 200
        assert response.content == dummy_storage._files[storage_id]
