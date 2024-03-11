from infrahub.api.menu import get_menu
from infrahub.database import InfrahubDatabase


def test_get_menu(aio_benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema):
    aio_benchmark(get_menu, branch=default_branch)
