from infrahub.core import registry
from infrahub.database import InfrahubDatabase


def test_schemabranch_duplicate(benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_schema = benchmark(schema.duplicate)
    assert new_schema.get_hash() == schema.get_hash()
