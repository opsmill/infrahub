from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.unit.core.schema_change.equivalence_cases import COMBINED_LOAD_CASES
from tests.unit.core.schema_change.helpers import (
    CombinedLoad,
    build_base_schema_root,
    build_direct_load_result,
    merge_schema_files,
    validate_candidate_schema,
)

RECORD_WRITE_RETRY_LIMIT = 3


@pytest.fixture(scope="session")
def equivalence_base_schema() -> SchemaBranch:
    """The processed internal, core and base schema, with an ID on every kind, attribute and relationship.

    Built once for the session, so no test may change it.
    """
    schema_roots = [SchemaRoot(**internal_schema), SchemaRoot(**core_models), build_base_schema_root()]
    schema = SchemaBranch(cache={}, name="main")
    for schema_root in schema_roots:
        schema_root.generate_uuid()
        schema.load_schema(schema=schema_root)
    schema.process()
    return schema


@pytest.fixture(scope="session")
def combined_base_schema() -> SchemaBranch:
    """The processed internal and core schema with the base kinds of every case of the combined load, with IDs.

    Built once for the session, so no test may change it.
    """
    schema_roots = [
        SchemaRoot(**internal_schema),
        SchemaRoot(**core_models),
        *(case.build_base_file() for case in COMBINED_LOAD_CASES),
    ]
    schema = SchemaBranch(cache={}, name="main")
    for schema_root in schema_roots:
        schema_root.generate_uuid()
        schema.load_schema(schema=schema_root)
    schema.process()
    return schema


@pytest.fixture(scope="session")
def combined_load(combined_base_schema: SchemaBranch) -> CombinedLoad:
    """The schema files of every case of the combined load, loaded directly and through operations.

    Built once for the session, so no test may change it.
    """
    base = combined_base_schema
    expected = build_direct_load_result(
        branch_schema=base,
        schema_root=merge_schema_files(case.schema_file(case.scope, base) for case in COMBINED_LOAD_CASES),
        default_branch_schema=base,
    )
    build_result = SchemaOperationBuilder().build(
        branch_schema=base,
        schema_root=merge_schema_files(case.schema_file(case.scope, base) for case in COMBINED_LOAD_CASES),
        default_branch_schema=base,
    )
    applied_schema = SchemaChangeApplier().apply(
        target_schema=base, operations=build_result.operations, default_branch_schema=base
    )
    actual = validate_candidate_schema(branch_schema=base, candidate_schema=applied_schema)
    return CombinedLoad(base=base, expected=expected, actual=actual)


@pytest.fixture
def fast_record_write_retries() -> Generator[None, None, None]:
    """Run a write that fails with a transient database error up to `RECORD_WRITE_RETRY_LIMIT` times, without waiting."""
    settings = config.SETTINGS.database
    original = (settings.retry_limit, settings.retry_base_delay, settings.retry_max_delay, settings.retry_jitter_max)
    settings.retry_limit = RECORD_WRITE_RETRY_LIMIT
    settings.retry_base_delay = 0.0
    settings.retry_max_delay = 0.0
    settings.retry_jitter_max = 0.0
    yield
    settings.retry_limit, settings.retry_base_delay, settings.retry_max_delay, settings.retry_jitter_max = original
