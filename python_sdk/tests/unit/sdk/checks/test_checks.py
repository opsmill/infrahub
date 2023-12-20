import pytest

from infrahub_sdk import InfrahubClient
from infrahub_sdk.checks import InfrahubCheck


async def test_class_init():
    class IFCheckNoQuery(InfrahubCheck):
        pass

    class IFCheckWithName(InfrahubCheck):
        name = "my_check"
        query = "my_query"

    class IFCheckNoName(InfrahubCheck):
        query = "my_query"

    with pytest.raises(ValueError) as exc:
        check = IFCheckNoQuery()

    assert "A query must be provided" in str(exc.value)

    check = IFCheckWithName()
    assert check.name == "my_check"
    assert check.root_directory is not None

    check = IFCheckNoName()
    assert check.name == "IFCheckNoName"

    check = IFCheckWithName(root_directory="/tmp")
    assert check.name == "my_check"
    assert check.root_directory == "/tmp"


async def test_async_init(client):
    class IFCheck(InfrahubCheck):
        query = "my_query"

    check = await IFCheck.init()
    assert isinstance(check.client, InfrahubClient)


async def test_validate_sync_async(mock_gql_query_my_query):
    class IFCheckAsync(InfrahubCheck):
        query = "my_query"

        async def validate(self):
            self.log_error("Not valid")

    class IFCheckSync(InfrahubCheck):
        query = "my_query"

        def validate(self):
            self.log_error("Not valid")

    check = await IFCheckAsync.init(branch="main")
    await check.run()

    assert check.passed is False

    check = await IFCheckSync.init(branch="main")
    await check.run()

    assert check.passed is False
