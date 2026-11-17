import pytest

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.unit.core.schema_change.helpers import build_base_schema_root


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
