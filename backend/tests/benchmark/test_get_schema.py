from infrahub.api.schema import get_schema
from infrahub.database import InfrahubDatabase


def test_get_schema(aio_benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema):
    aio_benchmark(get_schema, branch=default_branch, namespaces=None)
