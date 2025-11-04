from infrahub.database import InfrahubDatabase
from infrahub.telemetry.database import gather_database_information, get_server_info, get_system_info


async def test_get_server_info(db: InfrahubDatabase) -> None:
    servers = await get_server_info(db)
    assert len(servers) == 1


async def test_get_system_info(db: InfrahubDatabase) -> None:
    system_info = await get_system_info(db)
    assert system_info is not None


async def test_gather_database_information(db: InfrahubDatabase) -> None:
    data = await gather_database_information.fn(db)
    assert data is not None
