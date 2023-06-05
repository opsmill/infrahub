from infrahub.core.node import Node
from infrahub_client import InfrahubClient

from .test_infrahub_client import TestInfrahubClient as BaseTestInfrahubClient

# pylint: disable=unused-argument


class TestNoPaginationInfrahubClient(BaseTestInfrahubClient):
    pagination: bool = False

    async def test_get_one(self, client: InfrahubClient, session, init_db_base):
        obj1 = await Node.init(schema="Location", session=session)
        await obj1.new(session=session, name="jfk2", description="new york", type="site")
        await obj1.save(session=session)

        obj2 = await Node.init(schema="Location", session=session)
        await obj2.new(session=session, name="sfo2", description="san francisco", type="site")
        await obj2.save(session=session)
