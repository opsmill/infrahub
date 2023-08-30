from neo4j import AsyncSession


class InfrahubDatabase:
    """Base class for database access"""

    @property
    def session(self) -> AsyncSession:
        raise NotImplementedError()
