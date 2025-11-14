from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import InitializationError


async def get_or_load_schema_branch(db: InfrahubDatabase, branch: Branch) -> SchemaBranch:
    try:
        if registry.schema.has_schema_branch(branch.name):
            return registry.schema.get_schema_branch(branch.name)
    except InitializationError:
        schema_manager = SchemaManager()
        registry.schema = schema_manager
        internal_schema_root = SchemaRoot(**internal_schema)
        registry.schema.register_schema(schema=internal_schema_root)
    schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    return schema_branch
