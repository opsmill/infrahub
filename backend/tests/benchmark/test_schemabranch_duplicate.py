from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


def test_schemabranch_duplicate(
    benchmark: BenchmarkFixture, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_schema = benchmark(schema.duplicate)
    assert new_schema.get_hash() == schema.get_hash()
