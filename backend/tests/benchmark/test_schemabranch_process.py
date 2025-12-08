from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


def test_schemabranch_process(
    benchmark: BenchmarkFixture, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    benchmark(schema.process)
