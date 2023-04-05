import inspect

import pytest

from infrahub_client.branch import (
    BranchData,
    InfrahubBranchManager,
    InfrahubBranchManagerSync,
)

async_branch_methods = [method for method in dir(InfrahubBranchManager) if not method.startswith("_")]
sync_branch_methods = [method for method in dir(InfrahubBranchManagerSync) if not method.startswith("_")]


def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_branch_methods
    assert async_branch_methods == sync_branch_methods


@pytest.mark.parametrize("method", async_branch_methods)
def test_validate_method_signature(method):
    async_method = getattr(InfrahubBranchManager, method)
    sync_method = getattr(InfrahubBranchManagerSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == sync_sig.return_annotation


async def test_get_branches(client, mock_branches_list_query):  # pylint: disable=unused-argument
    branches = await client.branch.all()

    assert len(branches) == 2
    assert isinstance(branches["main"], BranchData)
