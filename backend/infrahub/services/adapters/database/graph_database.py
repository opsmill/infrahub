from neo4j import AsyncDriver, AsyncSession

from infrahub import config
from infrahub.services.adapters.database import InfrahubDatabase


class GraphDatabase(InfrahubDatabase):
    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    @property
    def session(self) -> AsyncSession:
        return self.driver.session(database=config.SETTINGS.database.database)
