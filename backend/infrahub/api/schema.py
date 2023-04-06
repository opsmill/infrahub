from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel
from starlette.responses import JSONResponse

from infrahub.api.dependencies import get_session
from infrahub.core import get_branch, registry
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.exceptions import BranchNotFound

router = APIRouter(prefix="/schema")


class SchemaReadAPI(BaseModel):
    nodes: List[NodeSchema]


class SchemaLoadAPI(SchemaRoot):
    version: str


@router.get("/")
async def get_schema(
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
) -> SchemaReadAPI:
    try:
        branch = await get_branch(session=session, branch=branch)
    except BranchNotFound as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    return SchemaReadAPI(
        nodes=[value for value in registry.get_full_schema(branch=branch).values() if isinstance(value, NodeSchema)]
    )


@router.post("/load")
async def load_schema(
    schema: SchemaLoadAPI,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
):
    try:
        branch = await get_branch(session=session, branch=branch)
    except BranchNotFound as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    schema.extend_nodes_with_interfaces()
    await SchemaManager.register_schema_to_registry(schema)
    await SchemaManager.load_schema_to_db(schema, session=session)

    return JSONResponse(status_code=202, content={})
