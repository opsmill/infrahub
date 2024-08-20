from abc import ABC, abstractmethod

from infrahub.database import InfrahubDatabase


class PermissionBackend(ABC):
    @abstractmethod
    async def load_permissions(self, db: InfrahubDatabase, account_id: str) -> dict[str, list[str]]: ...
