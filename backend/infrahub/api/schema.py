from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from fastapi import APIRouter, Depends, Query, Request
from infrahub_sdk.schema.generated.read import (
    BaseNodeSchemaRead,
    GenericSchemaRead,
    NodeSchemaRead,
    ProfileSchemaRead,
    TemplateSchemaRead,
)
from infrahub_sdk.schema.generated.write import InfrahubSchemaWrite
from infrahub_sdk.schema.validate import SchemaValidationWarningDetail
from infrahub_sdk.schema.validate import validate_schema as validate_write_schema
from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    ValidatorFunctionWrapHandler,
    computed_field,
    create_model,
    model_validator,
)
from starlette.responses import JSONResponse

from infrahub import lock
from infrahub.api.dependencies import get_branch_dep, get_context, get_current_user, get_db, get_permission_manager
from infrahub.api.exceptions import SchemaNotValidError
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.models import (  # noqa: TC001
    SchemaBranchHash,
    SchemaDiff,
    SchemaUpdateConstraintInfo,
    SchemaUpdateValidationResult,
)
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema import (
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    SchemaRoot,
    SchemaWarning,
    SchemaWarningKind,
    SchemaWarningType,
    TemplateSchema,
)
from infrahub.core.schema.constants import SchemaNamespace  # noqa: TC001
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.models.validate_migration import (
    SchemaValidateMigrationData,
    SchemaValidatorPathResponseData,
)
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.events import EventMeta
from infrahub.events.schema_action import SchemaUpdatedEvent, build_changed_elements_payload
from infrahub.exceptions import BranchStatusError, ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.permissions import define_global_permission_from_branch
from infrahub.types import ATTRIBUTE_PYTHON_TYPES
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import SCHEMA_VALIDATE_MIGRATION
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.auth.session import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices


log = get_logger()
router = APIRouter(prefix="/schema")


def _api_schema_from_schema[TApiSchema: BaseNodeSchemaRead](
    model: type[TApiSchema], schema: MainSchemaTypes
) -> TApiSchema:
    data = schema.model_dump()
    data["relationships"] = [
        relationship.model_dump() for relationship in schema.relationships if not relationship.internal_peer
    ]
    data["hash"] = schema.get_hash()
    return model(**data)


class SchemaReadAPI(BaseModel):
    main: str = Field(description="Main hash for the entire schema")
    nodes: list[NodeSchemaRead] = Field(default_factory=list)
    generics: list[GenericSchemaRead] = Field(default_factory=list)
    profiles: list[ProfileSchemaRead] = Field(default_factory=list)
    templates: list[TemplateSchemaRead] = Field(default_factory=list)
    namespaces: list[SchemaNamespace] = Field(default_factory=list)


def read_only_field_warnings(details: list[SchemaValidationWarningDetail]) -> list[SchemaWarning]:
    """Aggregate read-only field findings into one warning per field name.

    A payload read back from the schema API repeats the same read-only field on every node and
    attribute it contains, so grouping by field name keeps the response proportional to the number
    of distinct offending fields rather than to the size of the schema.
    """
    grouped: dict[str, list[SchemaWarningKind]] = {}
    for detail in details:
        kinds = grouped.setdefault(detail.name, [])
        if detail.kind is None:
            continue
        kind = SchemaWarningKind(kind=detail.kind, field=detail.element)
        if kind not in kinds:
            kinds.append(kind)

    return [
        SchemaWarning(
            type=SchemaWarningType.DEPRECATION,
            kinds=kinds,
            message=f"'{name}' is a read-only field, the submitted value is ignored",
        )
        for name, kinds in grouped.items()
    ]


class SchemaLoadAPI(InfrahubSchemaWrite):
    _internal_schema: SchemaRoot = PrivateAttr()
    _contract_warnings: list[SchemaWarning] = PrivateAttr(default_factory=list)

    @model_validator(mode="wrap")
    @classmethod
    def validate_write_contract(cls, data: Any, handler: ValidatorFunctionWrapHandler) -> Self:
        # Wrapped rather than run before validation so the warnings, which are only visible on the
        # raw payload, can be carried on the instance the handler returns.
        result = validate_write_schema(schema=data) if isinstance(data, dict) else None
        # Raising here turns the field-level messages into a single request-validation error.
        if result is not None and not result.valid:
            raise ValueError("; ".join(result.messages))

        instance: Self = handler(data)

        if result is not None:
            instance._contract_warnings = read_only_field_warnings(details=result.warnings)
        return instance

    @model_validator(mode="after")
    def build_internal_schema(self) -> Self:
        # Built here to surface validation errors at construction.
        self._internal_schema = SchemaRoot.model_validate(self.model_dump(exclude_none=True))
        return self

    @property
    def internal_schema(self) -> SchemaRoot:
        return self._internal_schema

    @property
    def contract_warnings(self) -> list[SchemaWarning]:
        return self._contract_warnings


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
    warnings: list[SchemaWarning] = Field(
        default_factory=list, description="Warnings encountered while loading the schema"
    )

    @computed_field
    def schema_updated(self) -> bool:
        """Indicates if the loading of the schema changed the existing schema."""
        return self.hash != self.previous_hash


def _merge_candidate_schemas(schemas: Sequence[SchemaRoot]) -> SchemaRoot:
    """Merge multiple schemas into one suitable to be loaded.

    Raises:
        ValueError: When the provided sequence of schemas is empty.

    """
    if not schemas:
        raise ValueError("Cannot merge an empty list of schemas")

    merged = schemas[0]
    for schema in schemas[1:]:
        merged = merged.merge(schema=schema)

    return merged


def evaluate_candidate_schemas(
    branch_schema: SchemaBranch, schemas_to_evaluate: Sequence[SchemaRoot]
) -> tuple[SchemaBranch, SchemaUpdateValidationResult]:
    candidate_schema = branch_schema.duplicate()
    try:
        schema = _merge_candidate_schemas(schemas=schemas_to_evaluate)

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
            _api_schema_from_schema(model=NodeSchemaRead, schema=value)
            for value in all_schemas
            if isinstance(value, NodeSchema) and value.namespace != "Internal"
        ],
        generics=[
            _api_schema_from_schema(model=GenericSchemaRead, schema=value)
            for value in all_schemas
            if isinstance(value, GenericSchema) and value.namespace != "Internal"
        ],
        profiles=[
            _api_schema_from_schema(model=ProfileSchemaRead, schema=value)
            for value in all_schemas
            if isinstance(value, ProfileSchema) and value.namespace != "Internal"
        ],
        templates=[
            _api_schema_from_schema(model=TemplateSchemaRead, schema=value)
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
) -> ProfileSchemaRead | NodeSchemaRead | GenericSchemaRead | TemplateSchemaRead:
    log.debug("schema_kind_request", branch=branch.name)

    schema = registry.schema.get(name=schema_kind, branch=branch, duplicate=False)

    api_schema: dict[str, type[ProfileSchemaRead | NodeSchemaRead | GenericSchemaRead | TemplateSchemaRead]] = {
        "profile": ProfileSchemaRead,
        "node": NodeSchemaRead,
        "generic": GenericSchemaRead,
        "template": TemplateSchemaRead,
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

    return _api_schema_from_schema(model=api_schema[key], schema=schema)


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


async def _validate_migrations(
    branch: Branch,
    candidate_schema: SchemaBranch,
    constraints: list[SchemaUpdateConstraintInfo],
    service: InfrahubServices,
    context: InfrahubContext,
) -> None:
    validate_migration_data = SchemaValidateMigrationData(
        branch=branch,
        schema_branch=candidate_schema,
        constraints=constraints,
    )
    responses = await service.workflow.execute_workflow(
        workflow=SCHEMA_VALIDATE_MIGRATION,
        context=context,
        expected_return=list[SchemaValidatorPathResponseData],
        parameters={"message": validate_migration_data},
        priority=WorkflowPriority.HIGH,
    )
    error_messages = [violation.message for response in responses for violation in response.violations]
    if error_messages:
        raise SchemaNotValidError(",\n".join(error_messages))


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
    try:
        await BranchStatusChecker(
            db=db, merge_write_blocker=MergeWriteBlocker(cache=request.app.state.service.cache)
        ).check(branch=branch)
    except BranchStatusError as err:
        raise ValidationError(input_value=str(err)) from err

    permission_manager.raise_for_permission(
        permission=define_global_permission_from_branch(
            permission=GlobalPermissions.MANAGE_SCHEMA, branch_name=branch.name
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
    warnings: list[SchemaWarning] = []
    candidate_schemas: list[SchemaRoot] = []
    for schema in schemas.schemas:
        internal_schema = schema.internal_schema
        candidate_schemas.append(internal_schema)
        errors += internal_schema.validate_reserved_names()
        warnings += internal_schema.gather_warnings()
        warnings += schema.contract_warnings

    if errors:
        raise SchemaNotValidError(message=", ".join(errors))

    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        original_hash = branch_schema.get_hash()

        candidate_schema, result = evaluate_candidate_schemas(
            branch_schema=branch_schema, schemas_to_evaluate=candidate_schemas
        )

        if not result.diff.all:
            return SchemaUpdate(hash=original_hash, previous_hash=original_hash, diff=result.diff, warnings=warnings)

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        await _validate_migrations(
            branch=branch,
            candidate_schema=candidate_schema,
            constraints=result.constraints,
            service=service,
            context=context,
        )

        origin_schema = branch_schema.duplicate()

        log.info("Schema has diff, will need to be updated", diff=result.diff.all, branch=branch.name)

        coordinator = SchemaUpdateCoordinator(
            db=db,
            schema_manager=registry.schema,
            rollbacker=GraphRollbacker(db=db),
            workflow=service.workflow,
        )

        updated_hash = await coordinator.execute(
            branch=branch,
            origin_schema=origin_schema,
            rollback_schema=origin_schema,
            candidate_schema=candidate_schema,
            at=Timestamp(),
            # The caller blocks on this request: a priority stamped into the
            # context puts the migration task tree in the interactive lane.
            context=context.model_copy(update={"priority": WorkflowPriority.HIGH}),
            migration_executor=MigrationExecutor.WORKFLOW,
            diff=result.diff,
            migrations=result.migrations,
            limit=result.diff.all,
            update_db=True,
            user_id=account_session.account_id,
        )

    await service.component.refresh_schema_hash(branches=[branch.name])

    log_data = get_log_data()
    request_id = log_data.get("request_id", "")
    event = SchemaUpdatedEvent(
        branch_name=branch.name,
        schema_hash=branch.active_schema_hash.main,
        changed_elements=build_changed_elements_payload(result.diff),
        meta=EventMeta(
            initiator_id=WORKER_IDENTITY,
            request_id=request_id,
            account_id=account_session.account_id,
            branch=branch,
            context=context.to_event_context(),
        ),
    )
    await service.event.send(event=event)

    return SchemaUpdate(hash=updated_hash, previous_hash=original_hash, diff=result.diff, warnings=warnings)


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
    warnings: list[SchemaWarning] = []
    candidate_schemas: list[SchemaRoot] = []
    for schema in schemas.schemas:
        internal_schema = schema.internal_schema
        candidate_schemas.append(internal_schema)
        errors += internal_schema.validate_reserved_names()
        warnings += internal_schema.gather_warnings()
        warnings += schema.contract_warnings

    if errors:
        raise SchemaNotValidError(message=", ".join(errors))

    branch_schema = registry.schema.get_schema_branch(name=branch.name)

    candidate_schema, result = evaluate_candidate_schemas(
        branch_schema=branch_schema, schemas_to_evaluate=candidate_schemas
    )

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
        priority=WorkflowPriority.HIGH,
    )
    error_messages = [violation.message for response in responses for violation in response.violations]
    if error_messages:
        raise SchemaNotValidError(message=",\n".join(error_messages))

    return JSONResponse(
        status_code=202,
        content={
            "diff": result.diff.model_dump(),
            "warnings": [warning.model_dump(mode="json") for warning in warnings],
        },
    )
