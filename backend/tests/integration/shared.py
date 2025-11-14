from typing import Any

from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import load_schema as load_schema_root


async def load_schema(db: InfrahubDatabase, schema: dict[str, Any]) -> None:
    await load_schema_root(db=db, schema=SchemaRoot(**schema), update_db=True)
