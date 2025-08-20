from infrahub.database import InfrahubDatabase

from .menu import default_menu
from .repository import MenuRepository


async def create_default_menu(db: InfrahubDatabase) -> None:
    repository = MenuRepository(db=db)
    await repository.create_menu(menu=default_menu)
