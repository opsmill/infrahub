from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from starlette.datastructures import UploadFile
from tests.adapters.storage import DummyObjectStorage
from tests.helpers.graphql import graphql
from tests.helpers.schema import FILE_CONTRACT
from tests.helpers.test_app import TestInfrahubApp

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.initialization import prepare_graphql_params

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClient
    from tests.helpers.test_client import InfrahubTestClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@dataclass
class FileObjectFixture:
    id: str
    file_name: str
    storage_id: str
    content: bytes


def create_upload_file(content: bytes, filename: str) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


class TestFileObject(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def dummy_storage(self) -> Generator[DummyObjectStorage, None, None]:
        storage = DummyObjectStorage()
        original_storage = registry._storage
        registry._storage = storage
        yield storage
        registry._storage = original_storage

    @pytest.fixture(scope="class")
    async def file_contract_schema(
        self, db: InfrahubDatabase, default_branch: Branch, initialize_registry: None
    ) -> None:
        schema_root = SchemaRoot(nodes=[FILE_CONTRACT])
        registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def file_object_in_main(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        file_contract_schema: None,
        dummy_storage: DummyObjectStorage,
    ) -> FileObjectFixture:
        file_content = b"Original file content in main branch"
        upload_file = create_upload_file(content=file_content, filename="main-document.pdf")

        query = """
        mutation CreateFileContract($file: Upload!) {
            TestingFileContractCreate(
                data: { description: { value: "Original in main" } }
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

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"file": upload_file},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestingFileContractCreate"]["ok"]

        obj_data = result.data["TestingFileContractCreate"]["object"]
        return FileObjectFixture(
            id=obj_data["id"],
            file_name=obj_data["file_name"]["value"],
            storage_id=obj_data["storage_id"]["value"],
            content=file_content,
        )

    @pytest.fixture(scope="class")
    async def feature_branch(self, client: InfrahubClient, file_object_in_main: FileObjectFixture) -> str:
        branch = await client.branch.create(branch_name="feature-file-update")
        return branch.name

    @pytest.fixture(scope="class")
    async def time_before_branch_update(self, feature_branch: str) -> str:
        return Timestamp().to_string()

    @pytest.fixture(scope="class")
    async def file_object_updated_in_branch(
        self,
        db: InfrahubDatabase,
        file_object_in_main: FileObjectFixture,
        feature_branch: str,
        time_before_branch_update: str,
        dummy_storage: DummyObjectStorage,
    ) -> FileObjectFixture:
        new_content = b"Updated file content in feature branch - different from main"
        new_file = create_upload_file(content=new_content, filename="branch-document.pdf")

        update_query = """
        mutation UpdateFileContract($id: String!, $file: Upload!) {
            TestingFileContractUpdate(
                data: {
                    id: $id
                    description: { value: "Updated in branch" }
                }
                file: $file
            ) {
                ok
                object {
                    id
                    file_name { value }
                    storage_id { value }
                    description { value }
                }
            }
        }
        """

        branch = await registry.get_branch(db=db, branch=feature_branch)
        branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=branch)

        result = await graphql(
            schema=gql_params.schema,
            source=update_query,
            context_value=gql_params.context,
            variable_values={"id": file_object_in_main.id, "file": new_file},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestingFileContractUpdate"]["ok"]

        obj_data = result.data["TestingFileContractUpdate"]["object"]
        return FileObjectFixture(
            id=obj_data["id"],
            file_name=obj_data["file_name"]["value"],
            storage_id=obj_data["storage_id"]["value"],
            content=new_content,
        )

    async def test_main_branch_has_original_file_via_graphql(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
    ) -> None:
        """Verify that querying the file object in main branch returns original attributes."""
        query = """
        query GetFileContract($id: ID!) {
            TestingFileContract(ids: [$id]) {
                edges {
                    node {
                        id
                        file_name { value }
                        storage_id { value }
                        description { value }
                    }
                }
            }
        }
        """

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"id": file_object_in_main.id},
        )

        assert not result.errors
        assert result.data
        edges = result.data["TestingFileContract"]["edges"]
        assert len(edges) == 1

        node = edges[0]["node"]
        assert node["file_name"]["value"] == file_object_in_main.file_name
        assert node["storage_id"]["value"] == file_object_in_main.storage_id
        assert node["description"]["value"] == "Original in main"

    async def test_feature_branch_has_updated_file_via_graphql(
        self,
        db: InfrahubDatabase,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
        feature_branch: str,
    ) -> None:
        """Verify that querying the file object in feature branch returns updated attributes."""
        query = """
        query GetFileContract($id: ID!) {
            TestingFileContract(ids: [$id]) {
                edges {
                    node {
                        id
                        file_name { value }
                        storage_id { value }
                        description { value }
                    }
                }
            }
        }
        """

        branch = await registry.get_branch(db=db, branch=feature_branch)
        branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=branch)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"id": file_object_in_main.id},
        )

        assert not result.errors
        assert result.data
        edges = result.data["TestingFileContract"]["edges"]
        assert len(edges) == 1

        node = edges[0]["node"]
        assert node["file_name"]["value"] == file_object_updated_in_branch.file_name
        assert node["storage_id"]["value"] == file_object_updated_in_branch.storage_id
        assert node["description"]["value"] == "Updated in branch"
        assert node["storage_id"]["value"] != file_object_in_main.storage_id

    async def test_main_branch_download_returns_original_content(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Verify that downloading file in main branch returns original content via all endpoints."""
        node_id = file_object_in_main.id
        storage_id = file_object_in_main.storage_id
        file_name = file_object_in_main.file_name
        expected_content = file_object_in_main.content
        headers = {"X-INFRAHUB-KEY": api_admin_token}

        response = await test_client.get(f"/api/storage/files/{node_id}", headers=headers)
        assert response.status_code == 200
        assert response.content == expected_content

        response_by_storage_id = await test_client.get(
            f"/api/storage/files/by-storage-id/{storage_id}", headers=headers
        )
        assert response_by_storage_id.status_code == 200
        assert response_by_storage_id.content == expected_content

        response_by_hfid = await test_client.get(
            "/api/storage/files/by-hfid/TestingFileContract", headers=headers, params={"hfid": file_name}
        )
        assert response_by_hfid.status_code == 200
        assert response_by_hfid.content == expected_content

    async def test_feature_branch_download_returns_updated_content(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
        feature_branch: str,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Verify that downloading file in feature branch returns updated content via all endpoints."""
        node_id = file_object_updated_in_branch.id
        storage_id = file_object_updated_in_branch.storage_id
        file_name = file_object_updated_in_branch.file_name
        expected_content = file_object_updated_in_branch.content
        headers = {"X-INFRAHUB-KEY": api_admin_token}
        params = {"branch": feature_branch}

        response = await test_client.get(f"/api/storage/files/{node_id}", headers=headers, params=params)
        assert response.status_code == 200
        assert response.content == expected_content

        response_by_storage_id = await test_client.get(
            f"/api/storage/files/by-storage-id/{storage_id}", headers=headers, params=params
        )
        assert response_by_storage_id.status_code == 200
        assert response_by_storage_id.content == expected_content

        response_by_hfid = await test_client.get(
            "/api/storage/files/by-hfid/TestingFileContract", headers=headers, params={**params, "hfid": file_name}
        )
        assert response_by_hfid.status_code == 200
        assert response_by_hfid.content == expected_content

    async def test_storage_has_both_file_versions(
        self,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Verify that storage contains both file versions with different storage IDs."""
        main_storage_id = file_object_in_main.storage_id
        branch_storage_id = file_object_updated_in_branch.storage_id

        assert main_storage_id != branch_storage_id
        assert main_storage_id in dummy_storage._files
        assert branch_storage_id in dummy_storage._files
        assert dummy_storage._files[main_storage_id] == file_object_in_main.content
        assert dummy_storage._files[branch_storage_id] == file_object_updated_in_branch.content

    async def test_time_travel_returns_original_file_before_update(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        file_object_in_main: FileObjectFixture,
        file_object_updated_in_branch: FileObjectFixture,
        feature_branch: str,
        time_before_branch_update: str,
        dummy_storage: DummyObjectStorage,
    ) -> None:
        """Verify that using the 'at' parameter returns the file version from that point in time via all endpoints."""
        node_id = file_object_in_main.id
        storage_id = file_object_in_main.storage_id
        file_name = file_object_in_main.file_name
        expected_content = file_object_in_main.content
        headers = {"X-INFRAHUB-KEY": api_admin_token}
        params = {"branch": feature_branch, "at": time_before_branch_update}

        response = await test_client.get(f"/api/storage/files/{node_id}", headers=headers, params=params)
        assert response.status_code == 200
        assert response.content == expected_content

        response_by_storage_id = await test_client.get(
            f"/api/storage/files/by-storage-id/{storage_id}", headers=headers, params=params
        )
        assert response_by_storage_id.status_code == 200
        assert response_by_storage_id.content == expected_content

        response_by_hfid = await test_client.get(
            "/api/storage/files/by-hfid/TestingFileContract", headers=headers, params={**params, "hfid": file_name}
        )
        assert response_by_hfid.status_code == 200
        assert response_by_hfid.content == expected_content
