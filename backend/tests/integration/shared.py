from typing import Any, Dict

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase


async def load_schema(db: InfrahubDatabase, schema: Dict[str, Any]):
    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()
    tmp_schema.load_schema(schema=SchemaRoot(**schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)
