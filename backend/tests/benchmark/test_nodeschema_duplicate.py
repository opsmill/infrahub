from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


def test_base_schema_duplicate_CoreProposedChange(
    benchmark: BenchmarkFixture, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    model = registry.schema.get(name="CoreProposedChange")
    new_node = benchmark(model.duplicate)
    assert new_node.kind == model.kind
