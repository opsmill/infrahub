from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field, model_validator
from starlette.responses import JSONResponse

from infrahub import config, lock
from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.models import SchemaBranchHash  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema_manager import SchemaNamespace  # noqa: TCH001
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import PermissionDeniedError, SchemaNotFound
from infrahub.log import get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from typing_extensions import Self


log = get_logger()
router = APIRouter(prefix="/schema")


class APISchemaMixin:
    @classmethod
    def from_schema(cls, schema: Union[NodeSchema, GenericSchema]) -> Self:
        schema_instance = schema.with_public_relationships()
        data = schema_instance.model_dump()
        data["hash"] = schema.get_hash()
        return cls(**data)


class APINodeSchema(NodeSchema, APISchemaMixin):
    api_kind: Optional[str] = Field(default=None, alias="kind", validate_default=True)
    hash: str

    @model_validator(mode="before")
    @classmethod
    def set_kind(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values["kind"] = f'{values["namespace"]}{values["name"]}'
        return values


class APIGenericSchema(GenericSchema, APISchemaMixin):
    api_kind: Optional[str] = Field(default=None, alias="kind", validate_default=True)
    hash: str

    @model_validator(mode="before")
    @classmethod
    def set_kind(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values["kind"] = f'{values["namespace"]}{values["name"]}'
        return values


class SchemaReadAPI(BaseModel):
    main: str = Field(description="Main hash for the entire schema")
    nodes: List[APINodeSchema] = Field(default_factory=list)
    generics: List[APIGenericSchema] = Field(default_factory=list)
    namespaces: List[SchemaNamespace] = Field(default_factory=list)


class SchemaLoadAPI(SchemaRoot):
    version: str


class SchemasLoadAPI(SchemaRoot):
    schemas: List[SchemaLoadAPI]


@router.get("")
@router.get("/")
async def get_schema(
    branch: Branch = Depends(get_branch_dep),
    namespaces: Union[List[str], None] = Query(default=None),
) -> SchemaReadAPI:
    log.debug("schema_request", branch=branch.name)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    all_schemas = schema_branch.get_schemas_for_namespaces(namespaces=namespaces)

    return SchemaReadAPI(
        main=registry.schema.get_schema_branch(name=branch.name).get_hash(),
        nodes=[
            APINodeSchema.from_schema(value)
            for value in all_schemas
            if isinstance(value, NodeSchema) and value.namespace != "Internal"
        ],
        generics=[
            APIGenericSchema.from_schema(value)
            for value in all_schemas
            if isinstance(value, GenericSchema) and value.namespace != "Internal"
        ],
        namespaces=schema_branch.get_namespaces(),
    )


@router.get("/summary")
async def get_schema_summary(
    branch: Branch = Depends(get_branch_dep),
) -> SchemaBranchHash:
    log.debug("schema_summary_request", branch=branch.name)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    return schema_branch.get_hash_full()


@router.get("/{schema_kind}")
async def get_schema_by_kind(
    schema_kind: str,
    branch: Branch = Depends(get_branch_dep),
) -> Union[APINodeSchema, APIGenericSchema]:
    log.debug("schema_kind_request", branch=branch.name)

    schema = registry.schema.get(name=schema_kind, branch=branch)

    if isinstance(schema, NodeSchema):
        return APINodeSchema.from_schema(schema=schema)
    if isinstance(schema, GenericSchema):
        return APIGenericSchema.from_schema(schema=schema)


@router.post("/load")
async def load_schema(
    schemas: SchemasLoadAPI,
    background_tasks: BackgroundTasks,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    _: str = Depends(get_current_user),
) -> JSONResponse:
    log.info("schema_load_request", branch=branch.name)

    errors: List[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise PermissionDeniedError(", ".join(errors))

    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)

        # We create a copy of the existing branch schema to do some validation before loading it.
        tmp_schema = branch_schema.duplicate()
        try:
            for schema in schemas.schemas:
                tmp_schema.load_schema(schema=schema)
            tmp_schema.process()
        except SchemaNotFound as exc:
            return JSONResponse(status_code=422, content={"error": exc.message})
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

        diff = tmp_schema.diff(branch_schema)

        if diff.all:
            log.info(f"Schema has diff, will need to be updated {diff.all}", branch=branch.name)
            async with db.start_transaction() as db:
                await registry.schema.update_schema_branch(
                    schema=tmp_schema, db=db, branch=branch.name, limit=diff.all, update_db=True
                )
                branch.update_schema_hash()
                log.info("Schema has been updated", branch=branch.name, hash=branch.schema_hash.main)
                await branch.save(db=db)

            if config.SETTINGS.broker.enable:
                message = messages.EventSchemaUpdate(
                    branch=branch.name,
                    meta=Meta(initiator_id=WORKER_IDENTITY),
                )
                background_tasks.add_task(services.send, message)

    return JSONResponse(status_code=202, content={})
