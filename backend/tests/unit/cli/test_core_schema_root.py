from infrahub.cli.db import build_core_schema_root
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch


def test_merged_core_schema_root_builds_the_same_schema_as_three_loads() -> None:
    three_loads = SchemaBranch(cache={}, name="main")
    three_loads.load_schema(schema=SchemaRoot(**internal_schema))
    three_loads.load_schema(schema=SchemaRoot(**core_models))
    three_loads.load_schema(schema=SchemaRoot(**deprecated_models))
    three_loads.process()
    merged = SchemaBranch(cache={}, name="main")
    merged.load_schema(schema=build_core_schema_root())
    merged.process()

    assert set(merged.all_names) == set(three_loads.all_names)
    assert merged.get_hash() == three_loads.get_hash()


def test_merged_core_schema_root_states_only_the_fields_of_the_core_models() -> None:
    core_tag = next(node for node in SchemaRoot(**core_models).nodes if node.kind == "BuiltinTag")
    merged_tag = next(node for node in build_core_schema_root().nodes if node.kind == "BuiltinTag")

    assert merged_tag.model_dump(exclude_unset=True) == core_tag.model_dump(exclude_unset=True)
