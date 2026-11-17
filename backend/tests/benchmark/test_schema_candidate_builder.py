import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.factory import build_schema_candidate_builder
from infrahub.core.schema_change.operations_check import NoSchemaOperationsCheck
from tests.helpers.schema import DEVICE_SCHEMA
from tests.unit.core.schema_change.helpers import build_direct_load_result

BENCHMARK_ROUNDS = 10
DEVICE_SCHEMA_LOAD_GROUP = "load-device-schema-on-internal-and-core"


@pytest.fixture(scope="module")
def internal_and_core_schema() -> SchemaBranch:
    """The processed internal and core schema, with an ID on every kind, attribute and relationship, as one read from the database has."""
    schema = SchemaBranch(cache={}, name="main")
    for schema_root in (SchemaRoot(**internal_schema), SchemaRoot(**core_models)):
        schema_root.generate_uuid()
        schema.load_schema(schema=schema_root)
    schema.process()
    return schema


def _new_device_schema_file() -> tuple[tuple[()], dict[str, SchemaRoot]]:
    return (), {"schema_root": DEVICE_SCHEMA.model_copy(deep=True)}


@pytest.mark.benchmark(group=DEVICE_SCHEMA_LOAD_GROUP)
def test_direct_load_of_device_schema(benchmark: BenchmarkFixture, internal_and_core_schema: SchemaBranch) -> None:
    def load(schema_root: SchemaRoot) -> None:
        build_direct_load_result(
            branch_schema=internal_and_core_schema,
            schema_root=schema_root,
            default_branch_schema=internal_and_core_schema,
        )

    benchmark.pedantic(load, setup=_new_device_schema_file, rounds=BENCHMARK_ROUNDS)


@pytest.mark.benchmark(group=DEVICE_SCHEMA_LOAD_GROUP)
def test_candidate_of_device_schema(benchmark: BenchmarkFixture, internal_and_core_schema: SchemaBranch) -> None:
    candidate_builder = build_schema_candidate_builder()
    assert isinstance(candidate_builder.operations_check, NoSchemaOperationsCheck)

    def load(schema_root: SchemaRoot) -> None:
        candidate_builder.from_schema_root(
            branch_schema=internal_and_core_schema,
            schema_root=schema_root,
            default_branch_schema=internal_and_core_schema,
        )

    benchmark.pedantic(load, setup=_new_device_schema_file, rounds=BENCHMARK_ROUNDS)
