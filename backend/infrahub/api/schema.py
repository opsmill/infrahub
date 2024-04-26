from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    IPvAnyAddress,
    IPvAnyNetwork,
    Json,
    computed_field,
    create_model,
    model_validator,
)
from starlette.responses import JSONResponse

from infrahub import config, lock
from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.api.exceptions import SchemaNotValidError
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.migrations.schema.runner import schema_migrations_runner
from infrahub.core.models import SchemaBranchHash, SchemaDiff  # noqa: TCH001
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema, SchemaRoot
from infrahub.core.schema_manager import SchemaBranch, SchemaNamespace, SchemaUpdateValidationResult  # noqa: TCH001
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import MigrationError, PermissionDeniedError
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
            values["kind"] = f'{values["namespace"]}{values["name"]}'
        return values


class APINodeSchema(NodeSchema, APISchemaMixin):
    api_kind: Optional[str] = Field(default=None, alias="kind", validate_default=True)
    hash: str


class APIGenericSchema(GenericSchema, APISchemaMixin):
    api_kind: Optional[str] = Field(default=None, alias="kind", validate_default=True)
    hash: str


class APIProfileSchema(ProfileSchema, APISchemaMixin):
    api_kind: Optional[str] = Field(default=None, alias="kind", validate_default=True)
    hash: str


class SchemaReadAPI(BaseModel):
    main: str = Field(description="Main hash for the entire schema")
    nodes: List[APINodeSchema] = Field(default_factory=list)
    generics: List[APIGenericSchema] = Field(default_factory=list)
    profiles: List[APIProfileSchema] = Field(default_factory=list)
    namespaces: List[SchemaNamespace] = Field(default_factory=list)


class SchemaLoadAPI(SchemaRoot):
    version: str


class SchemasLoadAPI(SchemaRoot):
    schemas: List[SchemaLoadAPI]


class SchemaUpdate(BaseModel):
    hash: str = Field(..., description="The new hash for the entire schema")
    previous_hash: str = Field(..., description="The previous hash for the entire schema")
    diff: SchemaDiff = Field(..., description="The modifications to the schema")

    @computed_field
    def schema_updated(self) -> bool:
        """Indicates if the loading of the schema changed the existing schema"""
        return self.hash != self.previous_hash


class JsonSchemaAttribute(BaseModel):
    name: str
    kind: str
    enum: Optional[List[Any]] = None
    regex: Optional[str] = None
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    unique: bool
    optional: bool
    default_value: Optional[Any] = None

    def to_json_schema_property(self):
        # Mapping internal kind to JSON Schema data types
        type_mapping = {
            "Text": "string",
            "Integer": "integer",
            "Float": "number",
            "Boolean": "boolean",
            "Date": "string",  # Date should be formatted as date-time
        }
        property_schema = {"type": type_mapping.get(self.kind, "string")}

        if self.enum:
            property_schema["enum"] = self.enum
        if self.regex:
            property_schema["pattern"] = self.regex
        if self.max_length is not None:
            property_schema["maxLength"] = self.max_length
        if self.min_length is not None:
            property_schema["minLength"] = self.min_length
        if self.default_value is not None:
            property_schema["default"] = self.default_value

        return self.name, property_schema


class InfraJsonSchema(BaseModel):
    id: str
    name: str
    namespace: str
    description: Optional[str] = None
    attributes: List[JsonSchemaAttribute]

    def generate_json_schema(self):
        properties = {}
        required = []

        for attribute in self.attributes:
            attr_name, attr_schema = attribute.to_json_schema_property()
            properties[attr_name] = attr_schema
            if not attribute.optional:
                required.append(attr_name)

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": self.name,
            "type": "object",
            "properties": properties,
            "required": required if required else None,
            "description": self.description,
        }


class JsonSchemaProperty(BaseModel):
    type: str
    enum: Optional[List[Union[str, int, float]]] = None
    default: Optional[Union[str, int, float]] = None
    pattern: Optional[str] = None
    max_length: Optional[int] = Field(None, alias="maxLength")
    min_length: Optional[int] = Field(None, alias="minLength")

    class Config:
        populate_by_name = True  # Allows the mixedCase aliases for min/max len


class JsonSchema(BaseModel):
    schema_spec: str = Field(alias="$schema", default="http://json-schema.org/draft-07/schema#")
    title: str
    type: str = "object"
    properties: Dict[str, JsonSchemaProperty]
    required: Optional[List[str]]
    description: Optional[str]

    class Config:
        populate_by_name = True  # This allows us to use $schema as a field name


def evaluate_candidate_schemas(
    branch_schema: SchemaBranch, schemas_to_evaluate: SchemasLoadAPI
) -> Tuple[SchemaBranch, SchemaUpdateValidationResult]:
    candidate_schema = branch_schema.duplicate()
    try:
        for schema in schemas_to_evaluate.schemas:
            candidate_schema.load_schema(schema=schema)
        candidate_schema.process()
    except ValueError as exc:
        raise SchemaNotValidError(message=str(exc)) from exc

    result = branch_schema.validate_update(other=candidate_schema)

    if result.errors:
        raise SchemaNotValidError(message=", ".join([error.to_string() for error in result.errors]))

    return candidate_schema, result


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
        profiles=[
            APIProfileSchema.from_schema(value)
            for value in all_schemas
            if isinstance(value, ProfileSchema) and value.namespace != "Internal"
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


@router.get("/json_schema/{schema_kind}")
async def get_json_schema_by_kind(
    schema_kind: str,
    branch: Branch = Depends(get_branch_dep),
) -> dict:
    log.debug("json_schema_kind_request", branch=branch.name)

    schema = registry.schema.get(name=schema_kind, branch=branch).model_dump()

    # Redefined ATTRIBUTE_TYPES with Python standard types or Pydantic compatible types
    JSON_ATTRIBUTE_TYPES = {
        "ID": int,  # Assuming IDs are integers
        "Dropdown": str,  # Dropdowns can be represented as strings
        "Text": str,
        "TextArea": str,
        "DateTime": datetime,
        "Email": EmailStr,
        "Password": str,  # Passwords can be any string
        "HashedPassword": str,  # Hashed passwords are also strings
        "URL": HttpUrl,
        "File": str,  # File paths or identifiers as strings
        "MacAddress": str,  # MAC addresses can be straightforward strings
        "Color": str,  # Colors often represented as hex strings
        "Number": float,  # Numbers can be floats for general use
        "Bandwidth": float,  # Bandwidth in some units, represented as a float
        "IPHost": IPvAnyAddress,
        "IPNetwork": IPvAnyNetwork,
        "Boolean": bool,
        "Checkbox": bool,  # Checkboxes represent boolean values
        "List": List[Any],  # Lists can contain any type of items
        "JSON": Json,  # Pydantic's Json type handles arbitrary JSON objects
        "Any": Any,  # Any type allowed
    }

    fields = {}
    for attr in schema["attributes"]:
        field_type = JSON_ATTRIBUTE_TYPES.get(attr["kind"], str)
        default_value = attr["default_value"] if attr["optional"] else ...
        field_info = Field(default=default_value, description=attr.get("description", ""))
        if attr.get("enum"):
            field_info = Field(default=default_value, description=attr.get("description", ""), enum=attr["enum"])
        fields[attr["name"]] = (field_type, field_info)

    # Use Pydantic's create_model to dynamically create the class
    json_schema = create_model(schema["name"], **fields).model_json_schema()

    json_schema["description"] = schema["description"]
    json_schema["$schema"] = "http://json-schema.org/draft-07/schema#"

    return json_schema


@router.post("/load")
async def load_schema(
    request: Request,
    schemas: SchemasLoadAPI,
    background_tasks: BackgroundTasks,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    _: Any = Depends(get_current_user),
) -> SchemaUpdate:
    service: InfrahubServices = request.app.state.service
    log.info("schema_load_request", branch=branch.name)

    errors: List[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise PermissionDeniedError(", ".join(errors))

    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        original_hash = branch_schema.get_hash()

        candidate_schema, result = evaluate_candidate_schemas(branch_schema=branch_schema, schemas_to_evaluate=schemas)

        if not result.diff.all:
            return SchemaUpdate(hash=original_hash, previous_hash=original_hash, diff=result.diff)

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        error_messages, _ = await schema_validators_checker(
            branch=branch, schema=candidate_schema, constraints=result.constraints, service=service
        )
        if error_messages:
            raise SchemaNotValidError(message=",\n".join(error_messages))

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

            if not branch.is_isolated and not branch.is_default and branch.has_schema_changes:
                branch.is_isolated = True
                log.info("Branch converted to isolated mode because the schema has changed", branch=branch.name)

            await branch.save(db=dbt)
            updated_branch = registry.schema.get_schema_branch(name=branch.name)
            updated_hash = updated_branch.get_hash()

        # ----------------------------------------------------------
        # Run the migrations
        # ----------------------------------------------------------
        error_messages = await schema_migrations_runner(
            branch=branch,
            new_schema=candidate_schema,
            previous_schema=origin_schema,
            migrations=result.migrations,
            service=service,
        )
        if error_messages:
            raise MigrationError(message=",\n".join(error_messages))

        if config.SETTINGS.broker.enable:
            message = messages.EventSchemaUpdate(
                branch=branch.name,
                meta=Meta(initiator_id=WORKER_IDENTITY),
            )
            background_tasks.add_task(services.send, message)

    await service.component.refresh_schema_hash(branches=[branch.name])

    return SchemaUpdate(hash=updated_hash, previous_hash=original_hash, diff=result.diff)


@router.post("/check")
async def check_schema(
    request: Request,
    schemas: SchemasLoadAPI,
    branch: Branch = Depends(get_branch_dep),
    _: Any = Depends(get_current_user),
) -> JSONResponse:
    service: InfrahubServices = request.app.state.service
    log.info("schema_check_request", branch=branch.name)

    errors: List[str] = []
    for schema in schemas.schemas:
        errors += schema.validate_namespaces()

    if errors:
        raise PermissionDeniedError(", ".join(errors))

    branch_schema = registry.schema.get_schema_branch(name=branch.name)

    candidate_schema, result = evaluate_candidate_schemas(branch_schema=branch_schema, schemas_to_evaluate=schemas)

    # ----------------------------------------------------------
    # Validate if the new schema is valid with the content of the database
    # ----------------------------------------------------------
    error_messages, _ = await schema_validators_checker(
        branch=branch, schema=candidate_schema, constraints=result.constraints, service=service
    )
    if error_messages:
        raise SchemaNotValidError(message=",\n".join(error_messages))

    return JSONResponse(status_code=202, content={"diff": result.diff.model_dump()})
