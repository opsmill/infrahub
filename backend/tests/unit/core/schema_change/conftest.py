from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.unit.core.schema_change.helpers import build_base_schema_root

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
