from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync


class TestDiffAPI(TestInfrahubDockerClient):
    def test_diff_data_api_endpoint(self, client_sync: InfrahubClientSync) -> None:
        branch_name = "test-branch"
        client_sync.branch.create(branch_name=branch_name)

        result = client_sync.branch.diff_data(branch_name=branch_name)

        assert isinstance(result, list)
