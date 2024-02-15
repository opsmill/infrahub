from infrahub.core import registry
from infrahub.database import InfrahubDatabase


def test_base_schema_duplicate_CoreProposedChange(
    benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema
):
    model = registry.schema.get(name="CoreProposedChange")
    new_node = benchmark(model.duplicate)
    assert new_node.kind == model.kind
