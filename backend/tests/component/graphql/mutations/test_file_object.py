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
