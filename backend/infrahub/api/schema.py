from typing import TYPE_CHECKING, List, Optional

from fastapi import APIRouter, Depends
from fastapi.logger import logger
from neo4j import AsyncSession
from pydantic import BaseModel
from starlette.responses import JSONResponse

from infrahub.api.dependencies import get_current_user, get_session
from infrahub.core import get_branch, registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.exceptions import SchemaNotFound
from infrahub.lock import registry as lock_registry
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

log = get_logger()
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
    log.info("schema_request", branch=branch.name)

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
    _: str = Depends(get_current_user),
):
    branch: Branch = await get_branch(session=session, branch=branch)

    # TODO we need to replace this lock with a distributed lock
    async with lock_registry.get_branch_schema_update():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)

        # We create a copy of the existing branch schema to do some validation before loading it.
        tmp_schema = branch_schema.duplicate()
        try:
            tmp_schema.load_schema(schema=schema)
            tmp_schema.process()
        except (SchemaNotFound, ValueError) as exc:
            return JSONResponse(status_code=422, content={"error": exc.message})

        diff = tmp_schema.diff(branch_schema)

        if diff.all:
            await registry.schema.update_schema_branch(
                schema=tmp_schema, session=session, branch=branch.name, limit=diff.all, update_db=True
            )
            branch.update_schema_hash()
            logger.info(f"{branch.name}: Schema has been updated, new hash {branch.schema_hash}")
            await branch.save(session=session)

        return JSONResponse(status_code=202, content={})
