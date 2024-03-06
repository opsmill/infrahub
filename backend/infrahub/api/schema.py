from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from starlette.responses import JSONResponse

from infrahub import config, lock
from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.migrations.schema.runner import schema_migrations_runner
from infrahub.core.models import SchemaBranchHash  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema_manager import SchemaNamespace  # noqa: TCH001
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import PermissionDeniedError, SchemaNotFound
from infrahub.log import get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.services import InfrahubServices


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

    api_schema: dict[str, type[Union[APINodeSchema, APIGenericSchema]]] = {
        "node": APINodeSchema,
        "generic": APIGenericSchema,
    }
    key = ""

    if isinstance(schema, NodeSchema):
        key = "node"
    if isinstance(schema, GenericSchema):
        key = "generic"

    return api_schema[key].from_schema(schema=schema)


@router.post("/load")
async def load_schema(  # noqa: PLR0911 pylint: disable=R0911,too-many-branches,too-many-statements
    request: Request,
    schemas: SchemasLoadAPI,
    background_tasks: BackgroundTasks,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    _: Union[str, list] = Depends(get_current_user),
) -> JSONResponse:
    service: InfrahubServices = request.app.state.service
    log.info("schema_load_request", branch=branch.name)

    errors: List[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise PermissionDeniedError(", ".join(errors))

    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)

        # ----------------------------------------------------------
        # Validate if the format of the new schema is valid
        # ----------------------------------------------------------
        # We create a copy of the existing branch schema to do some validation before loading it.
        candidate_schema = branch_schema.duplicate()
        try:
            for schema in schemas.schemas:
                candidate_schema.load_schema(schema=schema)
            candidate_schema.process()
        except SchemaNotFound as exc:
            return JSONResponse(status_code=422, content={"error": exc.message})
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

        result = branch_schema.validate_update(other=candidate_schema)

        if result.errors:
            return JSONResponse(
                status_code=422, content={"error": ", ".join([error.to_string() for error in result.errors])}
            )

        if not result.diff.all:
            return JSONResponse(status_code=202, content={})

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        error_messages, _ = await schema_validators_checker(
            branch=branch, schema=candidate_schema, constraints=result.constraints, service=service
        )
        if error_messages:
            return JSONResponse(status_code=422, content={"error": ",\n".join(error_messages)})

        # ----------------------------------------------------------
        # Update the schema
        # ----------------------------------------------------------
        log.info("Schema has diff, will need to be updated", diff=result.diff.all, branch=branch.name)
        async with db.start_transaction() as dbt:
            await registry.schema.update_schema_branch(
                schema=candidate_schema, db=dbt, branch=branch.name, limit=result.diff.all, update_db=True
            )
            branch.update_schema_hash()
            log.info("Schema has been updated", branch=branch.name, hash=branch.active_schema_hash.main)

            if not branch.is_isolated and not branch.is_default and branch.has_schema_changes:
                branch.is_isolated = True
                log.info("Branch converted to isolated mode because the schema has changed", branch=branch.name)

            await branch.save(db=dbt)

        # ----------------------------------------------------------
        # Run the migrations
        # ----------------------------------------------------------
        error_messages = await schema_migrations_runner(
            branch=branch, schema=candidate_schema, migrations=result.migrations, service=service
        )
        if error_messages:
            return JSONResponse(status_code=500, content={"error": ",\n".join(error_messages)})

        if config.SETTINGS.broker.enable:
            message = messages.EventSchemaUpdate(
                branch=branch.name,
                meta=Meta(initiator_id=WORKER_IDENTITY),
            )
            background_tasks.add_task(services.send, message)

    return JSONResponse(status_code=202, content={})
