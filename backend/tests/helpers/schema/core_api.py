from functools import cache

from infrahub_sdk.schema import NodeSchemaAPI

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch


@cache
def _core_schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process_inheritance()
    return schema_branch


def load_core_node_schema_api(kind: str) -> NodeSchemaAPI:
    """Return the API form of a core node schema, with its inherited attributes and relationships."""
    return NodeSchemaAPI(**_core_schema_branch().get(name=kind, duplicate=False).model_dump())
