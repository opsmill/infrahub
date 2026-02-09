from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from infrahub_sdk.schema.main import NodeSchemaAPI
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestFileObject(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def schema_file_contract(self) -> dict:
        return yaml.safe_load(Path(CURRENT_DIRECTORY / "test_files/file_contract.yml").open(encoding="utf-8"))

    async def test_load_schema(self, client: InfrahubClient, schema_file_contract: dict) -> None:
        """Load the FileContract schema that inherits from CoreFileObject and verify its structure."""
        result = await client.schema.load(schemas=[schema_file_contract], wait_until_converged=True)
        assert result.schema_updated
        assert await client.schema.in_sync()

        schema = await client.schema.get(kind="TestingFileContract")
        assert isinstance(schema, NodeSchemaAPI)
        assert "CoreFileObject" in schema.inherit_from

        attribute_names = {attr.name for attr in schema.attributes}
        inherited_attributes = {"checksum", "file_name", "file_size", "file_type", "storage_id"}
        assert inherited_attributes.issubset(attribute_names)

    async def test_create_file_object_with_upload_from_bytes(self, client: InfrahubClient) -> None:
        """Create a file object using upload_from_bytes and verify it can be downloaded."""
        file_content = b"This is a test contract document content."
        file_name = "contract-2026.pdf"

        contract = await client.create(kind="TestingFileContract", data={"description": "Annual contract for 2026"})
        contract.upload_from_bytes(content=file_content, name=file_name)
        await contract.save()

        retrieved = await client.get(kind="TestingFileContract", id=contract.id)
        assert retrieved.file_name.value == file_name
        assert retrieved.description.value == "Annual contract for 2026"

        downloaded_content = await retrieved.download_file()
        assert downloaded_content == file_content

    async def test_update_file_object_with_new_file(self, client: InfrahubClient) -> None:
        """Update an existing file object with a new file and verify the change."""
        initial_content = b"Initial contract content"
        updated_content = b"Updated contract content with new terms"

        contract = await client.create(kind="TestingFileContract", data={"description": "Contract to be updated"})
        contract.upload_from_bytes(content=initial_content, name="initial.pdf")
        await contract.save()

        initial_storage_id = contract.storage_id.value

        contract_to_update = await client.get(kind="TestingFileContract", id=contract.id)
        contract_to_update.upload_from_bytes(content=updated_content, name="updated.pdf")
        await contract_to_update.save()

        updated_contract = await client.get(kind="TestingFileContract", id=contract.id)
        assert updated_contract.file_name.value == "updated.pdf"
        assert updated_contract.storage_id.value != initial_storage_id

        downloaded = await updated_contract.download_file()
        assert downloaded == updated_content

    async def test_file_object_branch_isolation(self, client: InfrahubClient) -> None:
        """Verify that file changes on a branch do not affect main branch."""
        main_content = b"Main branch contract content"
        branch_content = b"Branch-specific contract content"

        contract = await client.create(kind="TestingFileContract", data={"description": "Contract for branch test"})
        contract.upload_from_bytes(content=main_content, name="main-contract.pdf")
        await contract.save()
        contract_id = contract.id

        contract = await client.get(kind="TestingFileContract", id=contract_id)
        main_storage_id = contract.storage_id.value

        branch = await client.branch.create(branch_name="file-update-branch")

        branch_client = client.clone(branch=branch.name)
        branch_contract = await branch_client.get(kind="TestingFileContract", id=contract_id)
        branch_contract.upload_from_bytes(content=branch_content, name="branch-contract.pdf")
        await branch_contract.save()

        main_contract = await client.get(kind="TestingFileContract", id=contract_id)
        assert main_contract.file_name.value == "main-contract.pdf"
        assert main_contract.storage_id.value == main_storage_id
        main_downloaded = await main_contract.download_file()
        assert main_downloaded == main_content

        branch_retrieved = await branch_client.get(kind="TestingFileContract", id=contract_id)
        assert branch_retrieved.file_name.value == "branch-contract.pdf"
        assert branch_retrieved.storage_id.value != main_storage_id
        branch_downloaded = await branch_retrieved.download_file()
        assert branch_downloaded == branch_content

    async def test_download_file_to_disk(self, client: InfrahubClient, tmp_path: Path) -> None:
        """Verify that files can be streamed directly to disk."""
        file_content = b"Large file content that should be streamed to disk"

        contract = await client.create(
            kind="TestingFileContract", data={"description": "Contract for disk download test"}
        )
        contract.upload_from_bytes(content=file_content, name="large-contract.pdf")
        await contract.save()

        retrieved = await client.get(kind="TestingFileContract", id=contract.id)

        dest_path = tmp_path / "downloaded-contract.pdf"
        bytes_written = await retrieved.download_file(dest=dest_path)

        assert bytes_written == len(file_content)
        assert dest_path.exists()
        assert dest_path.read_bytes() == file_content

    async def test_file_object_with_vendor_relationship(self, client: InfrahubClient) -> None:
        """Verify that file objects work correctly with relationships to other nodes."""
        vendor = await client.create(
            kind="TestingVendor",
            data={
                "name": "Acme Corporation",
                "contact_email": "contracts@acme.example.com",
                "website": "https://acme.example.com",
            },
        )
        await vendor.save()

        file_content = b"Service Level Agreement between parties"
        contract = await client.create(
            kind="TestingFileContract", data={"description": "SLA with Acme Corporation", "vendor": vendor}
        )
        contract.upload_from_bytes(content=file_content, name="acme-sla.pdf")
        await contract.save()

        retrieved_contract = await client.get(kind="TestingFileContract", id=contract.id, include=["vendor"])
        assert retrieved_contract.description.value == "SLA with Acme Corporation"
        assert retrieved_contract.file_name.value == "acme-sla.pdf"

        await retrieved_contract.vendor.fetch()
        assert retrieved_contract.vendor.peer.name.value == "Acme Corporation"

        downloaded = await retrieved_contract.download_file()
        assert downloaded == file_content

        retrieved_vendor = await client.get(kind="TestingVendor", id=vendor.id, include=["contracts"])
        await retrieved_vendor.contracts.fetch()
        assert len(retrieved_vendor.contracts.peers) == 1
        assert retrieved_vendor.contracts.peers[0].id == contract.id
