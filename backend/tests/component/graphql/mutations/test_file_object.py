from __future__ import annotations

import hashlib
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.adapters.storage import DummyObjectStorage
from tests.helpers.graphql import graphql
from tests.helpers.schema import FILE_CONTRACT

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def create_upload_file(content: bytes, filename: str) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


class TestFileObjectMutations:
    """Tests for FileObject GraphQL mutations with file upload."""

    @pytest.fixture(scope="class")
    def dummy_storage(self) -> Generator[DummyObjectStorage, None, None]:
        storage = DummyObjectStorage()
        original_storage = registry._storage
        registry._storage = storage
        yield storage
        registry._storage = original_storage

    @pytest.fixture(scope="class")
    async def file_contract_schema(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, register_core_models_schema_scope_class: None
    ) -> None:
        schema_root = SchemaRoot(nodes=[FILE_CONTRACT])
        registry.schema.register_schema(schema=schema_root, branch=default_branch_scope_class.name)

    async def test_create_file_object_mutation(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test creating a FileObject node via GraphQL mutation with file upload."""
        file_content = b"%PDF-1.4 test contract content"
        upload_file = create_upload_file(content=file_content, filename="contract.pdf")

        query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: {
                    description: { value: "Test contract" }
                }
                file: $file
            ) {
                ok
                object {
                    id
                    file_name { value }
                    file_size { value }
                    file_type { value }
                    checksum { value }
                    storage_id { value }
                    description { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": upload_file},
        )

        assert not result.errors, f"GraphQL errors: {result.errors}"
        assert result.data is not None
        assert result.data["TestingFileContractCreate"]["ok"] is True

        obj_data = result.data["TestingFileContractCreate"]["object"]
        assert obj_data["file_name"]["value"] == "contract.pdf"
        assert obj_data["file_size"]["value"] == len(file_content)
        assert obj_data["description"]["value"] == "Test contract"
        assert obj_data["checksum"]["value"] == hashlib.sha1(file_content, usedforsecurity=False).hexdigest()
        assert obj_data["storage_id"]["value"]

        storage_id = obj_data["storage_id"]["value"]
        assert storage_id in dummy_storage._files
        assert dummy_storage._files[storage_id] == file_content

    async def test_create_file_object_without_file_fails(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that creating a FileObject without required file parameter fails."""
        files_before = len(dummy_storage._files)

        query = """
        mutation CreateFileContract {
            TestingFileContractCreate(
                data: {
                    description: { value: "Test contract" }
                }
            ) {
                ok
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={},
        )

        assert result.errors
        assert (
            "Field 'TestingFileContractCreate' argument 'file' of type 'Upload!' is required, but it was not provided."
            in str(result.errors[0])
        )
        assert len(dummy_storage._files) == files_before

    async def test_update_file_object_with_new_file(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test updating a FileObject with a new file replaces the stored file."""
        initial_content = b"initial content"
        initial_file = create_upload_file(content=initial_content, filename="initial.txt")

        create_query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Initial" } }
                file: $file
            ) {
                ok
                object { id storage_id { value } }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=create_query,
            context_value=gql_params.context,
            variable_values={"file": initial_file},
        )

        assert create_result.errors is None
        node_id = create_result.data["TestingFileContractCreate"]["object"]["id"]
        initial_storage_id = create_result.data["TestingFileContractCreate"]["object"]["storage_id"]["value"]

        # Update with new file
        new_content = b"updated content with more data"
        new_file = create_upload_file(content=new_content, filename="updated.txt")

        update_query = """
        mutation UpdateFileContract($id: String!, $file: Upload) {
            TestingFileContractUpdate(
                data: {
                    id: $id
                    description: { value: "Updated" }
                }
                file: $file
            ) {
                ok
                object {
                    id
                    file_name { value }
                    file_size { value }
                    storage_id { value }
                    description { value }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        update_result = await graphql(
            schema=gql_params.schema,
            source=update_query,
            context_value=gql_params.context,
            variable_values={"id": node_id, "file": new_file},
        )

        assert update_result.errors is None, f"GraphQL errors: {update_result.errors}"
        assert update_result.data["TestingFileContractUpdate"]["ok"] is True

        obj_data = update_result.data["TestingFileContractUpdate"]["object"]
        assert obj_data["file_name"]["value"] == "updated.txt"
        assert obj_data["file_size"]["value"] == len(new_content)
        assert obj_data["description"]["value"] == "Updated"
        assert obj_data["storage_id"]["value"] != initial_storage_id  # New storage ID

        new_storage_id = obj_data["storage_id"]["value"]
        assert initial_storage_id in dummy_storage._files
        assert new_storage_id in dummy_storage._files
        assert dummy_storage._files[new_storage_id] == new_content

    async def test_update_file_object_without_file_preserves_existing(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that updating without a file preserves existing file attributes."""
        initial_content = b"original file content"
        initial_file = create_upload_file(content=initial_content, filename="original.pdf")

        create_query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Original" } }
                file: $file
            ) {
                ok
                object {
                    id
                    file_name { value }
                    storage_id { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=create_query,
            context_value=gql_params.context,
            variable_values={"file": initial_file},
        )

        assert create_result.errors is None
        node_id = create_result.data["TestingFileContractCreate"]["object"]["id"]
        original_file_name = create_result.data["TestingFileContractCreate"]["object"]["file_name"]["value"]
        original_storage_id = create_result.data["TestingFileContractCreate"]["object"]["storage_id"]["value"]

        files_before_update = len(dummy_storage._files)

        # Update only description, no file
        update_query = """
        mutation UpdateFileContract($id: String!) {
            TestingFileContractUpdate(
                data: {
                    id: $id
                    description: { value: "Updated description only" }
                }
            ) {
                ok
                object {
                    file_name { value }
                    storage_id { value }
                    description { value }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        update_result = await graphql(
            schema=gql_params.schema,
            source=update_query,
            context_value=gql_params.context,
            variable_values={"id": node_id},
        )

        assert update_result.errors is None, f"GraphQL errors: {update_result.errors}"
        assert update_result.data["TestingFileContractUpdate"]["ok"] is True

        obj_data = update_result.data["TestingFileContractUpdate"]["object"]
        assert obj_data["file_name"]["value"] == original_file_name
        assert obj_data["storage_id"]["value"] == original_storage_id
        assert obj_data["description"]["value"] == "Updated description only"

        assert len(dummy_storage._files) == files_before_update
        assert original_storage_id in dummy_storage._files

    async def test_create_file_object_stores_correct_content(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that file content is correctly passed to storage backend."""
        file_content = b"specific test content for verification"
        upload_file = create_upload_file(content=file_content, filename="test.bin")

        query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Test" } }
                file: $file
            ) {
                ok
                object { storage_id { value } }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": upload_file},
        )

        assert not result.errors

        storage_id = result.data["TestingFileContractCreate"]["object"]["storage_id"]["value"]
        assert storage_id in dummy_storage._files
        assert dummy_storage._files[storage_id] == file_content

    async def test_create_file_object_node_persisted_in_database(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that created FileObject node is persisted in database with correct attributes."""
        file_content = b"database persistence test"
        upload_file = create_upload_file(content=file_content, filename="persist.txt")

        query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Persisted" } }
                file: $file
            ) {
                ok
                object { id }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": upload_file},
        )

        assert not result.errors
        node_id = result.data["TestingFileContractCreate"]["object"]["id"]

        node = await NodeManager.get_one(db=db, id=node_id, branch=default_branch_scope_class)
        assert node is not None
        assert node.file_name.value == "persist.txt"
        assert node.file_size.value == len(file_content)
        assert node.description.value == "Persisted"
        assert node.checksum.value == hashlib.sha1(file_content, usedforsecurity=False).hexdigest()
        assert node.storage_id.value

    async def test_create_file_object_not_stored_on_mutation_failure(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that uploaded file is not stored in storage when mutation fails."""
        file_content = b"file that should not be stored"
        upload_file = create_upload_file(content=file_content, filename="cleanup.txt")
        files_before = len(dummy_storage._files)

        query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Should fail" } }
                file: $file
            ) {
                ok
                object { id storage_id { value } }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        with patch("infrahub.graphql.mutations.main.create_node", side_effect=Exception("Simulated failure")):
            result = await graphql(
                schema=gql_params.schema,
                source=query,
                context_value=gql_params.context,
                variable_values={"file": upload_file},
            )

        assert result.errors is not None
        assert "Simulated failure" in str(result.errors[0])
        assert len(dummy_storage._files) == files_before

    async def test_upsert_file_object_creates_when_not_exists(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that upsert creates a new FileObject when it doesn't exist."""
        file_content = b"upsert content"
        upload_file = create_upload_file(content=file_content, filename="upsert.txt")
        files_before = len(dummy_storage._files)

        query = """
        mutation UpsertFileContract($file: Upload!) {
            TestingFileContractUpsert(
                data: { description: { value: "Upserted" } }
                file: $file
            ) {
                ok
                object {
                    id
                    file_name { value }
                    storage_id { value }
                    checksum { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": upload_file},
        )

        assert result.errors is None, f"GraphQL errors: {result.errors}"
        assert result.data["TestingFileContractUpsert"]["ok"] is True

        obj_data = result.data["TestingFileContractUpsert"]["object"]
        assert obj_data["file_name"]["value"] == "upsert.txt"
        assert obj_data["storage_id"]["value"]
        assert obj_data["checksum"]["value"] == hashlib.sha1(file_content, usedforsecurity=False).hexdigest()

        assert len(dummy_storage._files) == files_before + 1

    async def test_upsert_file_object_same_file_is_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that upserting with the same file doesn't create duplicate storage."""
        file_content = b"idempotent content"

        # First upsert - creates the node
        first_file = create_upload_file(content=file_content, filename="idempotent.txt")

        query = """
        mutation UpsertFileContract($file: Upload!) {
            TestingFileContractUpsert(
                data: { description: { value: "First upsert" } }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        first_result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": first_file},
        )

        assert first_result.errors is None
        first_storage_id = first_result.data["TestingFileContractUpsert"]["object"]["storage_id"]["value"]
        first_checksum = first_result.data["TestingFileContractUpsert"]["object"]["checksum"]["value"]
        node_id = first_result.data["TestingFileContractUpsert"]["object"]["id"]
        files_after_first = len(dummy_storage._files)

        # Second upsert with same file content - should be idempotent
        second_file = create_upload_file(content=file_content, filename="idempotent.txt")

        upsert_by_id_query = """
        mutation UpsertFileContract($id: String!, $file: Upload!) {
            TestingFileContractUpsert(
                data: {
                    id: $id
                    description: { value: "Second upsert" }
                }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                    description { value }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        second_result = await graphql(
            schema=gql_params.schema,
            source=upsert_by_id_query,
            context_value=gql_params.context,
            variable_values={"id": node_id, "file": second_file},
        )

        assert second_result.errors is None, f"GraphQL errors: {second_result.errors}"
        assert second_result.data["TestingFileContractUpsert"]["ok"] is True

        obj_data = second_result.data["TestingFileContractUpsert"]["object"]
        # Storage ID should NOT change - same file content
        assert obj_data["storage_id"]["value"] == first_storage_id
        assert obj_data["checksum"]["value"] == first_checksum
        # Description should be updated
        assert obj_data["description"]["value"] == "Second upsert"

        # No new files should be stored
        assert len(dummy_storage._files) == files_after_first

    async def test_upsert_file_object_different_file_creates_new_storage(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that upserting with a different file creates new storage."""
        first_content = b"first content"
        second_content = b"different content"

        # First upsert - creates the node
        first_file = create_upload_file(content=first_content, filename="first.txt")

        query = """
        mutation UpsertFileContract($file: Upload!) {
            TestingFileContractUpsert(
                data: { description: { value: "First" } }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        first_result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": first_file},
        )

        assert first_result.errors is None
        first_storage_id = first_result.data["TestingFileContractUpsert"]["object"]["storage_id"]["value"]
        node_id = first_result.data["TestingFileContractUpsert"]["object"]["id"]
        files_after_first = len(dummy_storage._files)

        # Second upsert with different file content - should create new storage
        second_file = create_upload_file(content=second_content, filename="second.txt")

        upsert_by_id_query = """
        mutation UpsertFileContract($id: String!, $file: Upload!) {
            TestingFileContractUpsert(
                data: {
                    id: $id
                    description: { value: "Second" }
                }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                    file_name { value }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        second_result = await graphql(
            schema=gql_params.schema,
            source=upsert_by_id_query,
            context_value=gql_params.context,
            variable_values={"id": node_id, "file": second_file},
        )

        assert second_result.errors is None, f"GraphQL errors: {second_result.errors}"
        assert second_result.data["TestingFileContractUpsert"]["ok"] is True

        obj_data = second_result.data["TestingFileContractUpsert"]["object"]
        # Storage ID SHOULD change - different file content
        assert obj_data["storage_id"]["value"] != first_storage_id
        assert obj_data["checksum"]["value"] == hashlib.sha1(second_content, usedforsecurity=False).hexdigest()
        assert obj_data["file_name"]["value"] == "second.txt"

        # New file should be stored
        assert len(dummy_storage._files) == files_after_first + 1
        # Both files should exist
        assert first_storage_id in dummy_storage._files
        assert obj_data["storage_id"]["value"] in dummy_storage._files

    async def test_upsert_file_object_hfid_collision_is_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Test that upsert via HFID collision is idempotent for same file content.

        When upsert triggers an HFIDViolatedError (node found via HFID computed from
        data fields, not from 'id' or 'hfid' key), we check if the uploaded file has
        the same checksum as the existing node. If so, we delete the duplicate and
        preserve the original storage_id.
        """
        file_content = b"hfid collision content"

        # First: create a file object via Create mutation
        first_file = create_upload_file(content=file_content, filename="hfid_collision.txt")

        create_query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Original" } }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                }
            }
        }
        """

        default_branch_scope_class.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_result = await graphql(
            schema=gql_params.schema,
            source=create_query,
            context_value=gql_params.context,
            variable_values={"file": first_file},
        )

        assert create_result.errors is None
        first_storage_id = create_result.data["TestingFileContractCreate"]["object"]["storage_id"]["value"]
        first_checksum = create_result.data["TestingFileContractCreate"]["object"]["checksum"]["value"]
        files_after_create = len(dummy_storage._files)

        # Second: upsert with same filename (HFID match) and same content, but WITHOUT providing 'id'
        # This triggers the HFIDViolatedError path in mutate_upsert
        second_file = create_upload_file(content=file_content, filename="hfid_collision.txt")

        upsert_query = """
        mutation UpsertFileContract($file: Upload!) {
            TestingFileContractUpsert(
                data: { description: { value: "Via HFID collision" } }
                file: $file
            ) {
                ok
                object {
                    id
                    storage_id { value }
                    checksum { value }
                    description { value }
                }
            }
        }
        """

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        upsert_result = await graphql(
            schema=gql_params.schema,
            source=upsert_query,
            context_value=gql_params.context,
            variable_values={"file": second_file},
        )

        assert upsert_result.errors is None, f"GraphQL errors: {upsert_result.errors}"
        assert upsert_result.data["TestingFileContractUpsert"]["ok"] is True

        obj_data = upsert_result.data["TestingFileContractUpsert"]["object"]
        # Description should be updated (confirming we updated existing node)
        assert obj_data["description"]["value"] == "Via HFID collision"

        # Same checksum - storage_id should be preserved (idempotent behavior)
        assert obj_data["storage_id"]["value"] == first_storage_id
        assert obj_data["checksum"]["value"] == first_checksum

        # No duplicate file - storage count unchanged
        assert len(dummy_storage._files) == files_after_create
        assert first_storage_id in dummy_storage._files
