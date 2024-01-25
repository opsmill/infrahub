from infrahub.core import registry
from infrahub.database import InfrahubDatabase


def test_schemabranch_process(benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    benchmark.pedantic(schema.process, iterations=5)
