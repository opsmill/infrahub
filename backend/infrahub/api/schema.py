from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.logger import logger
from neo4j import AsyncSession
from pydantic import BaseModel, Field, root_validator
from starlette.responses import JSONResponse

from infrahub import lock
from infrahub.api.dependencies import get_branch_dep, get_current_user, get_session
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.exceptions import SchemaNotFound
from infrahub.log import get_logger

log = get_logger()
router = APIRouter(prefix="/schema")


class APINodeSchema(NodeSchema):
    api_kind: Optional[str] = Field(default=None, alias="kind")

    @root_validator(pre=True)
    @classmethod
    def set_kind(
        cls,
        values,
    ):
        values["kind"] = f'{values["namespace"]}{values["name"]}'
        return values


class APIGenericSchema(GenericSchema):
    api_kind: Optional[str] = Field(default=None, alias="kind")

    @root_validator(pre=True)
    @classmethod
    def set_kind(
        cls,
        values,
    ):
        values["kind"] = f'{values["namespace"]}{values["name"]}'
        return values


class SchemaReadAPI(BaseModel):
    nodes: List[APINodeSchema]
    generics: List[APIGenericSchema]


class SchemaLoadAPI(SchemaRoot):
    version: str


@router.get("")
@router.get("/")
async def get_schema(
    branch: Branch = Depends(get_branch_dep),
) -> SchemaReadAPI:
    log.info("schema_request", branch=branch.name)

    full_schema = registry.schema.get_full(branch=branch)

    return SchemaReadAPI(
        nodes=[value.dict() for value in full_schema.values() if isinstance(value, NodeSchema)],
        generics=[value.dict() for value in full_schema.values() if isinstance(value, GenericSchema)],
    )


@router.post("/load")
async def load_schema(
    schema: SchemaLoadAPI,
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    _: str = Depends(get_current_user),
) -> JSONResponse:
    # TODO we need to replace this lock with a distributed lock
    async with lock.registry.get_branch_schema_update():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)

        # We create a copy of the existing branch schema to do some validation before loading it.
        tmp_schema = branch_schema.duplicate()
        try:
            tmp_schema.load_schema(schema=schema)
            tmp_schema.process()
        except SchemaNotFound as exc:
            return JSONResponse(status_code=422, content={"error": exc.message})
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

        diff = tmp_schema.diff(branch_schema)

        if diff.all:
            await registry.schema.update_schema_branch(
                schema=tmp_schema, session=session, branch=branch.name, limit=diff.all, update_db=True
            )
            branch.update_schema_hash()
            logger.info(f"{branch.name}: Schema has been updated, new hash {branch.schema_hash}")
            await branch.save(session=session)

        return JSONResponse(status_code=202, content={})
