from fastapi import Request
from neo4j import AsyncSession

import infrahub.config as config


async def get_session(request: Request) -> AsyncSession:
    session = request.app.state.db.session(database=config.SETTINGS.database.database)
    try:
        yield session
    finally:
        await session.close()
