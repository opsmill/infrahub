import pytest

from infrahub.api.menu import get_menu
from infrahub.core.initialization import create_default_menu
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def init_menu(db: InfrahubDatabase, default_branch, register_core_models_schema):
    await create_default_menu(db=db)


def test_get_menu(aio_benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema, init_menu):
    aio_benchmark(get_menu, db=db, branch=default_branch, account_session=None)
