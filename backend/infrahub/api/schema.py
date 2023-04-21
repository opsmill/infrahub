from typing import List, Optional

from fastapi import APIRouter, Depends
from neo4j import AsyncSession
from pydantic import BaseModel
from starlette.responses import JSONResponse

from infrahub.api.dependencies import get_session
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.exceptions import SchemaNotFound

router = APIRouter(prefix="/schema")


class SchemaReadAPI(BaseModel):
    nodes: List[NodeSchema]
    generics: List[GenericSchema]


class SchemaLoadAPI(SchemaRoot):
    version: str


@router.get("/")
async def get_schema(
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
) -> SchemaReadAPI:
    branch = await get_branch(session=session, branch=branch)

    full_schema = registry.schema.get_full(branch=branch)

    return SchemaReadAPI(
        nodes=[value for value in full_schema.values() if isinstance(value, NodeSchema)],
        generics=[value for value in full_schema.values() if isinstance(value, GenericSchema)],
    )


@router.post("/load")
async def load_schema(
    schema: SchemaLoadAPI,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
):
    branch: Branch = await get_branch(session=session, branch=branch)

    branch_schema = registry.schema.get_schema_branch(name=branch.name)

    # We create a copy of the existing branch schema to do some validation before loading it.
    tmp_schema = branch_schema.duplicate()
    try:
        tmp_schema.load_schema(schema=schema)
        tmp_schema.process()
    except (SchemaNotFound, ValueError) as exc:
        return JSONResponse(status_code=422, content={"error": exc.message})

    diff = tmp_schema.diff(branch_schema)

    await registry.schema.update_schema_branch(
        schema=tmp_schema, session=session, branch=branch.name, limit=diff.all, update_db=True
    )

    return JSONResponse(status_code=202, content={})
