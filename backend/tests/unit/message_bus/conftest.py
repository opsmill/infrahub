import pytest

from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
async def rpc_client():
    return InfrahubRpcClientTesting()
