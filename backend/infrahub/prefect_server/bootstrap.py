import asyncio

from prefect.server.database import provide_database_interface
from prefect.server.models.block_registration import run_block_auto_registration


async def init_prefect() -> None:
    db = provide_database_interface()

    await db.create_db()
    session = await db.session()

    async with session:
        await run_block_auto_registration(session=session)


if __name__ == "__main__":
    asyncio.run(init_prefect())
