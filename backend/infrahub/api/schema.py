from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from fastapi import APIRouter, Depends, Query, Request
from pydantic import (
    BaseModel,
    Field,
    computed_field,
    create_model,
    model_validator,
)
from starlette.responses import JSONResponse

from infrahub import lock
from infrahub.api.dependencies import get_branch_dep, get_context, get_current_user, get_db, get_permission_manager
from infrahub.api.exceptions import SchemaNotValidError
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.models import (  # noqa: TC001
    SchemaBranchHash,
    SchemaDiff,
    SchemaUpdateValidationResult,
)
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema, SchemaRoot, TemplateSchema
from infrahub.core.schema.constants import SchemaNamespace  # noqa: TC001
from infrahub.core.validators.models.validate_migration import (
    SchemaValidateMigrationData,
    SchemaValidatorPathResponseData,
)
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.events import EventMeta
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.exceptions import MigrationError
from infrahub.log import get_log_data, get_logger
from infrahub.types import ATTRIBUTE_PYTHON_TYPES
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import SCHEMA_APPLY_MIGRATION, SCHEMA_VALIDATE_MIGRATION

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.auth import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices


log = get_logger()
router = APIRouter(prefix="/schema")


class APISchemaMixin:
    @classmethod
    def from_schema(cls, schema: MainSchemaTypes) -> Self:
        data = schema.model_dump()
        data["relationships"] = [
            relationship.model_dump() for relationship in schema.relationships if not relationship.internal_peer
        ]
        data["hash"] = schema.get_hash()
        return cls(**data)

    @model_validator(mode="before")
    @classmethod
    def set_kind(cls, values: Any) -> Any:
        if isinstance(values, dict):
            values["kind"] = f"{values['namespace']}{values['name']}"
        return values


class APINodeSchema(NodeSchema, APISchemaMixin):
    api_kind: str | None = Field(default=None, alias="kind", validate_default=True)
    hash: str


class APIGenericSchema(GenericSchema, APISchemaMixin):
    api_kind: str | None = Field(default=None, alias="kind", validate_default=True)
    hash: str


class APIProfileSchema(ProfileSchema, APISchemaMixin):
    api_kind: str | None = Field(default=None, alias="kind", validate_default=True)
    hash: str


class APITemplateSchema(TemplateSchema, APISchemaMixin):
    api_kind: str | None = Field(default=None, alias="kind", validate_default=True)
    hash: str


class SchemaReadAPI(BaseModel):
    main: str = Field(description="Main hash for the entire schema")
    nodes: list[APINodeSchema] = Field(default_factory=list)
    generics: list[APIGenericSchema] = Field(default_factory=list)
    profiles: list[APIProfileSchema] = Field(default_factory=list)
    templates: list[APITemplateSchema] = Field(default_factory=list)
    namespaces: list[SchemaNamespace] = Field(default_factory=list)


class SchemaLoadAPI(SchemaRoot):
    version: str


class SchemasLoadAPI(BaseModel):
    schemas: list[SchemaLoadAPI]


class JSONSchema(BaseModel):
    title: str | None = Field(None, description="Title of the schema")
    description: str | None = Field(None, description="Description of the schema")
    type: str = Field(..., description="Type of the schema element (e.g., 'object', 'array', 'string')")
    properties: dict[str, Any] | None = Field(None, description="Properties of the object if type is 'object'")
    items: dict[str, Any] | list[dict[str, Any]] | None = Field(
        None, description="Items of the array if type is 'array'"
    )
    required: list[str] | None = Field(None, description="List of required properties if type is 'object'")
    schema_spec: str | None = Field(None, alias="$schema", description="Schema version identifier")
    additional_properties: bool | dict[str, Any] | None = Field(
        None, description="Specifies whether additional properties are allowed", alias="additionalProperties"
    )


class SchemaUpdate(BaseModel):
    hash: str = Field(..., description="The new hash for the entire schema")
    previous_hash: str = Field(..., description="The previous hash for the entire schema")
    diff: SchemaDiff = Field(..., description="The modifications to the schema")

    @computed_field
    def schema_updated(self) -> bool:
        """Indicates if the loading of the schema changed the existing schema"""
        return self.hash != self.previous_hash


def _merge_candidate_schemas(schemas: Sequence[SchemaRoot]) -> SchemaRoot:
    """Merge multiple schemas into one suitable to be loaded."""
    if not schemas:
        raise ValueError("Cannot merge an empty list of schemas")

    merged = schemas[0]
    for schema in schemas[1:]:
        merged = merged.merge(schema=schema)

    return merged


def evaluate_candidate_schemas(
    branch_schema: SchemaBranch, schemas_to_evaluate: SchemasLoadAPI
) -> tuple[SchemaBranch, SchemaUpdateValidationResult]:
    candidate_schema = branch_schema.duplicate()
    schema = _merge_candidate_schemas(schemas=schemas_to_evaluate.schemas)

    try:
        candidate_schema.load_schema(schema=schema)
        candidate_schema.process()

        schema_diff = branch_schema.diff(other=candidate_schema)
        candidate_schema.validate_node_deletions(diff=schema_diff)
    except ValueError as exc:
        raise SchemaNotValidError(message=str(exc)) from exc

    result = branch_schema.validate_update(other=candidate_schema, diff=schema_diff)

    if result.errors:
        raise SchemaNotValidError(message=", ".join([error.to_string() for error in result.errors]))

    return candidate_schema, result


@router.get("")
async def get_schema(
    branch: Branch = Depends(get_branch_dep),
    namespaces: list[str] | None = Query(default=None),
    _: AccountSession = Depends(get_current_user),
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
        profiles=[
            APIProfileSchema.from_schema(value)
            for value in all_schemas
            if isinstance(value, ProfileSchema) and value.namespace != "Internal"
        ],
        templates=[
            APITemplateSchema.from_schema(value)
            for value in all_schemas
            if isinstance(value, TemplateSchema) and value.namespace != "Internal"
        ],
        namespaces=schema_branch.get_namespaces(),
    )


@router.get("/summary")
async def get_schema_summary(
    branch: Branch = Depends(get_branch_dep), _: AccountSession = Depends(get_current_user)
) -> SchemaBranchHash:
    log.debug("schema_summary_request", branch=branch.name)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    return schema_branch.get_hash_full()


@router.get("/{schema_kind}")
async def get_schema_by_kind(
    schema_kind: str, branch: Branch = Depends(get_branch_dep), _: AccountSession = Depends(get_current_user)
) -> APIProfileSchema | APINodeSchema | APIGenericSchema | APITemplateSchema:
    log.debug("schema_kind_request", branch=branch.name)

    schema = registry.schema.get(name=schema_kind, branch=branch, duplicate=False)

    api_schema: dict[str, type[APIProfileSchema | APINodeSchema | APIGenericSchema | APITemplateSchema]] = {
        "profile": APIProfileSchema,
        "node": APINodeSchema,
        "generic": APIGenericSchema,
        "template": APITemplateSchema,
    }
    key = ""

    if isinstance(schema, ProfileSchema):
        key = "profile"
    if isinstance(schema, NodeSchema):
        key = "node"
    if isinstance(schema, GenericSchema):
        key = "generic"
    if isinstance(schema, TemplateSchema):
        key = "template"

    return api_schema[key].from_schema(schema=schema)


@router.get("/json_schema/{schema_kind}")
async def get_json_schema_by_kind(
    schema_kind: str, branch: Branch = Depends(get_branch_dep), _: AccountSession = Depends(get_current_user)
) -> JSONSchema:
    log.debug("json_schema_kind_request", branch=branch.name)

    fields: dict[str, Any] = {}

    schema = registry.schema.get(name=schema_kind, branch=branch)

    for attr in schema.attributes:
        field_type = ATTRIBUTE_PYTHON_TYPES[attr.kind]

        default_value = attr.default_value if attr.optional else ...
        field_info = Field(default=default_value, description=attr.description)
        if attr.enum or attr.kind == "Dropdown":
            extras: dict[str, Any]
            if attr.kind == "Dropdown" and attr.choices:
                extras = {"enum": [choice.name for choice in attr.choices]}
            else:
                extras = {"enum": attr.enum}
            field_info = Field(default=default_value, description=attr.description, json_schema_extra=extras)
        fields[attr.name] = (field_type, field_info)

    # Use Pydantic's create_model to dynamically create the class, ignore types because fields are Any, and mypy hates that
    json_schema = create_model(schema.name, **fields).model_json_schema()

    json_schema["description"] = schema.description
    json_schema["$schema"] = "http://json-schema.org/draft-07/schema#"

    return json_schema


@router.post("/load")
async def load_schema(
    request: Request,
    schemas: SchemasLoadAPI,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    account_session: AccountSession = Depends(get_current_user),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    context: InfrahubContext = Depends(get_context),
) -> SchemaUpdate:
    permission_manager.raise_for_permission(
        permission=GlobalPermission(
            action=GlobalPermissions.MANAGE_SCHEMA.value,
            decision=(
                PermissionDecision.ALLOW_DEFAULT
                if branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
                else PermissionDecision.ALLOW_OTHER
            ).value,
        )
    )

    if branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch):
        permission_manager.raise_for_permission(
            permission=GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_DEFAULT.value
            ),
        )

    service: InfrahubServices = request.app.state.service
    log.info("schema_load_request", branch=branch.name)

    errors: list[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise SchemaNotValidError(message=", ".join(errors))

    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        original_hash = branch_schema.get_hash()

        candidate_schema, result = evaluate_candidate_schemas(branch_schema=branch_schema, schemas_to_evaluate=schemas)

        if not result.diff.all:
            return SchemaUpdate(hash=original_hash, previous_hash=original_hash, diff=result.diff)

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        validate_migration_data = SchemaValidateMigrationData(
            branch=branch,
            schema_branch=candidate_schema,
            constraints=result.constraints,
        )
        responses = await service.workflow.execute_workflow(
            workflow=SCHEMA_VALIDATE_MIGRATION,
            context=context,
            expected_return=list[SchemaValidatorPathResponseData],
            parameters={"message": validate_migration_data},
        )
        error_messages = [violation.message for response in responses for violation in response.violations]
        if error_messages:
            raise SchemaNotValidError(",\n".join(error_messages))

        # ----------------------------------------------------------
        # Update the schema
        # ----------------------------------------------------------
        origin_schema = branch_schema.duplicate()
        log.info("Schema has diff, will need to be updated", diff=result.diff.all, branch=branch.name)
        async with db.start_transaction() as dbt:
            await registry.schema.update_schema_branch(
                schema=candidate_schema,
                db=dbt,
                branch=branch.name,
                diff=result.diff,
                limit=result.diff.all,
                update_db=True,
            )
            branch.update_schema_hash()
            log.info("Schema has been updated", branch=branch.name, hash=branch.active_schema_hash.main)

            # NOTE shouldn't be required anymore, will need to cleanup later
            if not branch.is_isolated and not branch.is_default and branch.has_schema_changes:
                branch.is_isolated = True
                log.info("Branch converted to isolated mode because the schema has changed", branch=branch.name)

            await branch.save(db=dbt)
            updated_branch = registry.schema.get_schema_branch(name=branch.name)
            updated_hash = updated_branch.get_hash()

        # ----------------------------------------------------------
        # Run the migrations
        # ----------------------------------------------------------
        apply_migration_data = SchemaApplyMigrationData(
            branch=branch,
            new_schema=candidate_schema,
            previous_schema=origin_schema,
            migrations=result.migrations,
        )
        migration_error_msgs = await service.workflow.execute_workflow(
            workflow=SCHEMA_APPLY_MIGRATION,
            context=context,
            expected_return=list[str],
            parameters={"message": apply_migration_data},
        )

        if migration_error_msgs:
            raise MigrationError(message=",\n".join(migration_error_msgs))

    await service.component.refresh_schema_hash(branches=[branch.name])

    log_data = get_log_data()
    request_id = log_data.get("request_id", "")
    event = SchemaUpdatedEvent(
        branch_name=branch.name,
        schema_hash=branch.active_schema_hash.main,
        meta=EventMeta(
            initiator_id=WORKER_IDENTITY,
            request_id=request_id,
            account_id=account_session.account_id,
            branch=branch,
            context=context,
        ),
    )
    await service.event.send(event=event)

    return SchemaUpdate(hash=updated_hash, previous_hash=original_hash, diff=result.diff)


@router.post("/check")
async def check_schema(
    request: Request,
    schemas: SchemasLoadAPI,
    branch: Branch = Depends(get_branch_dep),
    context: InfrahubContext = Depends(get_context),
    _: AccountSession = Depends(get_current_user),
) -> JSONResponse:
    service: InfrahubServices = request.app.state.service
    log.info("schema_check_request", branch=branch.name)

    errors: list[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise SchemaNotValidError(message=", ".join(errors))

    branch_schema = registry.schema.get_schema_branch(name=branch.name)

    candidate_schema, result = evaluate_candidate_schemas(branch_schema=branch_schema, schemas_to_evaluate=schemas)

    # ----------------------------------------------------------
    # Validate if the new schema is valid with the content of the database
    # ----------------------------------------------------------
    validate_migration_data = SchemaValidateMigrationData(
        branch=branch,
        schema_branch=candidate_schema,
        constraints=result.constraints,
    )
    responses = await service.workflow.execute_workflow(
        workflow=SCHEMA_VALIDATE_MIGRATION,
        context=context,
        expected_return=list[SchemaValidatorPathResponseData],
        parameters={"message": validate_migration_data},
    )
    error_messages = [violation.message for response in responses for violation in response.violations]
    if error_messages:
        raise SchemaNotValidError(message=",\n".join(error_messages))

    return JSONResponse(status_code=202, content={"diff": result.diff.model_dump()})
