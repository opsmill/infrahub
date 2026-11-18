from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, assert_never

from graphene import Boolean, Field, InputObjectType, Mutation, String
from pydantic_core import to_jsonable_python

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import RESTRICTED_NAMESPACES, GlobalPermissions
from infrahub.core.manager import NodeManager
from infrahub.core.schema import DropdownChoice, GenericSchema, NodeSchema
from infrahub.core.schema_change.enums import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.factory import build_schema_candidate_builder, build_schema_change_recorder
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.events import EventMeta
from infrahub.events.schema_action import SchemaUpdatedEvent, build_changed_elements_payload
from infrahub.exceptions import ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.log import get_log_data, get_logger
from infrahub.permissions import define_global_permission_from_branch
from infrahub.utils import InfrahubStringEnum
from infrahub.worker import WORKER_IDENTITY

from ..types import DropdownFields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo
    from pydantic import JsonValue

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.services import InfrahubServices

    from ..initialization import GraphqlContext

log = get_logger()


def _validate_schema_permission(graphql_context: GraphqlContext) -> None:
    graphql_context.active_permissions.raise_for_permission(
        permission=define_global_permission_from_branch(
            permission=GlobalPermissions.MANAGE_SCHEMA, branch_name=graphql_context.branch.name
        )
    )


class AttributeListProperty(InfrahubStringEnum):
    """The list properties of an attribute that a dropdown or enum mutation changes."""

    CHOICES = "choices"
    ENUM = "enum"


@dataclass(frozen=True)
class DropdownChoiceAddition:
    choice: DropdownChoice

    @property
    def property_name(self) -> AttributeListProperty:
        return AttributeListProperty.CHOICES

    def build_list(self, kind: str, attribute: AttributeSchema) -> list[DropdownChoice]:
        """Return the choices of `attribute` with the choice added.

        Raises:
            ValidationError: The attribute already has a choice of that name.

        """
        choices = attribute.choices or []
        if any(entry.name == self.choice.name for entry in choices):
            raise ValidationError(
                f"The dropdown value {self.choice.name} already exists on {kind} in attribute {attribute.name}"
            )
        return [*choices, self.choice]


@dataclass(frozen=True)
class DropdownChoiceRemoval:
    name: str

    @property
    def property_name(self) -> AttributeListProperty:
        return AttributeListProperty.CHOICES

    def build_list(self, kind: str, attribute: AttributeSchema) -> list[DropdownChoice]:
        """Return the choices of `attribute` without the choice of that name.

        Raises:
            ValidationError: The attribute has no choice of that name, or it is the attribute's last choice.

        """
        choices = attribute.choices or []
        if not any(entry.name == self.name for entry in choices):
            raise ValidationError(
                f"The dropdown value {self.name} does not exists on {kind} in attribute {attribute.name}"
            )
        if len(choices) == 1:
            raise ValidationError(f"Unable to remove the last dropdown on {kind} in attribute {attribute.name}")
        return [entry for entry in choices if entry.name != self.name]


@dataclass(frozen=True)
class EnumValueAddition:
    value: str

    @property
    def property_name(self) -> AttributeListProperty:
        return AttributeListProperty.ENUM

    def build_list(self, kind: str, attribute: AttributeSchema) -> list[str]:
        """Return the enum values of `attribute` with the value added.

        Raises:
            ValidationError: The attribute already has the value.

        """
        enum_values = attribute.enum or []
        if self.value in enum_values:
            raise ValidationError(f"The enum value {self.value} already exists on {kind} in attribute {attribute.name}")
        return [*enum_values, self.value]


@dataclass(frozen=True)
class EnumValueRemoval:
    value: str

    @property
    def property_name(self) -> AttributeListProperty:
        return AttributeListProperty.ENUM

    def build_list(self, kind: str, attribute: AttributeSchema) -> list[str]:
        """Return the enum values of `attribute` without the value.

        Raises:
            ValidationError: The attribute does not have the value, or it is the attribute's last value.

        """
        enum_values = attribute.enum or []
        if self.value not in enum_values:
            raise ValidationError(
                f"The enum value {self.value} does not exists on {kind} in attribute {attribute.name}"
            )
        if len(enum_values) == 1:
            raise ValidationError(f"Unable to remove the last enum on {kind} in attribute {attribute.name}")
        return [entry for entry in enum_values if entry != self.value]


type AttributeListChange = DropdownChoiceAddition | DropdownChoiceRemoval | EnumValueAddition | EnumValueRemoval


class SchemaEnumInput(InputObjectType):
    kind = String(required=True)
    attribute = String(required=True)
    enum = String(required=True)


class SchemaDropdownRemoveInput(InputObjectType):
    kind = String(required=True)
    attribute = String(required=True)
    dropdown = String(required=True)


class SchemaDropdownAddInput(SchemaDropdownRemoveInput):
    color = String(required=False)
    description = String(required=False)
    label = String(required=False)


class SchemaDropdownAdd(Mutation):
    class Arguments:
        data = SchemaDropdownAddInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()
    object = Field(DropdownFields)

    @classmethod
    @retry_db_transaction(name="schema_dropdown_add")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: SchemaDropdownAddInput,
        context: ContextInput | None = None,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        _validate_schema_permission(graphql_context=graphql_context)
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        kind = graphql_context.db.schema.get(name=str(data.kind), branch=graphql_context.branch.name, duplicate=False)
        attribute = str(data.attribute)
        validate_kind_dropdown(kind=kind, attribute=attribute)
        dropdown = str(data.dropdown)
        choice = DropdownChoice(name=dropdown, color=data.color, label=data.label, description=data.description)

        await apply_attribute_property_change(
            kind=kind.kind,
            attribute=attribute,
            change=DropdownChoiceAddition(choice=choice),
            branch=graphql_context.branch,
            db=graphql_context.db,
            account_id=graphql_context.active_account_session.account_id,
            service=graphql_context.active_service,
            context=graphql_context.get_context(),
        )

        kind = graphql_context.db.schema.get(name=str(data.kind), branch=graphql_context.branch.name, duplicate=False)
        attrib = kind.get_attribute(attribute)
        dropdown_entry = {}
        success = False

        for entry in attrib.choices:
            if entry.name == dropdown:
                dropdown_entry = {
                    "value": dropdown,
                    "color": entry.color,
                    "label": entry.label,
                    "description": entry.description,
                }
                success = True

        return cls(object=dropdown_entry, ok=success)


class SchemaDropdownRemove(Mutation):
    class Arguments:
        data = SchemaDropdownRemoveInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="schema_dropdown_remove")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: SchemaDropdownRemoveInput,
        context: ContextInput | None = None,
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context

        _validate_schema_permission(graphql_context=graphql_context)
        kind = graphql_context.db.schema.get(name=str(data.kind), branch=graphql_context.branch.name, duplicate=False)
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        attribute = str(data.attribute)
        validate_kind_dropdown(kind=kind, attribute=attribute)
        dropdown = str(data.dropdown)
        nodes_with_dropdown = await NodeManager.query(
            db=graphql_context.db,
            schema=kind.kind,
            filters={f"{attribute}__value": dropdown},
            branch=graphql_context.branch,
        )
        if nodes_with_dropdown:
            raise ValidationError(f"There are still {kind.kind} objects using this dropdown")

        await apply_attribute_property_change(
            kind=kind.kind,
            attribute=attribute,
            change=DropdownChoiceRemoval(name=dropdown),
            branch=graphql_context.branch,
            db=graphql_context.db,
            account_id=graphql_context.active_account_session.account_id,
            service=graphql_context.active_service,
            context=graphql_context.get_context(),
        )

        return {"ok": True}


class SchemaEnumAdd(Mutation):
    class Arguments:
        data = SchemaEnumInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="schema_dropdown_add")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: SchemaEnumInput,
        context: ContextInput | None = None,
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context

        _validate_schema_permission(graphql_context=graphql_context)
        kind = graphql_context.db.schema.get(name=str(data.kind), branch=graphql_context.branch.name, duplicate=False)
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        attribute = str(data.attribute)
        enum = str(data.enum)
        validate_kind_enum(kind=kind, attribute=attribute)

        await apply_attribute_property_change(
            kind=kind.kind,
            attribute=attribute,
            change=EnumValueAddition(value=enum),
            branch=graphql_context.branch,
            db=graphql_context.db,
            account_id=graphql_context.active_account_session.account_id,
            service=graphql_context.active_service,
            context=graphql_context.get_context(),
        )

        return {"ok": True}


class SchemaEnumRemove(Mutation):
    class Arguments:
        data = SchemaEnumInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="schema_enum_remove")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: SchemaEnumInput,
        context: ContextInput | None = None,
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context

        _validate_schema_permission(graphql_context=graphql_context)
        kind = graphql_context.db.schema.get(name=str(data.kind), branch=graphql_context.branch.name, duplicate=False)
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        attribute = str(data.attribute)
        enum = str(data.enum)
        validate_kind_enum(kind=kind, attribute=attribute)
        nodes_with_enum = await NodeManager.query(
            db=graphql_context.db,
            schema=kind.kind,
            filters={f"{attribute}__value": enum},
            branch=graphql_context.branch,
        )
        if nodes_with_enum:
            raise ValidationError(f"There are still {kind.kind} objects using this enum")

        await apply_attribute_property_change(
            kind=kind.kind,
            attribute=attribute,
            change=EnumValueRemoval(value=enum),
            branch=graphql_context.branch,
            db=graphql_context.db,
            account_id=graphql_context.active_account_session.account_id,
            service=graphql_context.active_service,
            context=graphql_context.get_context(),
        )

        return {"ok": True}


def validate_kind_dropdown(kind: GenericSchema | NodeSchema, attribute: str) -> None:
    validate_kind(kind=kind, attribute=attribute)
    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]
    if matching_attribute and matching_attribute[0].kind != "Dropdown":
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is not a Dropdown")


def validate_kind_enum(kind: GenericSchema | NodeSchema, attribute: str) -> None:
    validate_kind(kind=kind, attribute=attribute)
    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]
    if not matching_attribute[0].enum:
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is not an enum")


def validate_kind(kind: GenericSchema | NodeSchema, attribute: str) -> None:
    if kind.namespace in RESTRICTED_NAMESPACES:
        raise ValidationError(f"Operation not allowed for {kind.kind} in restricted namespace {kind.namespace}")
    if attribute not in kind.attribute_names:
        raise ValidationError(f"Attribute {attribute} does not exist on {kind.kind}")

    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]

    if matching_attribute[0].inherited:
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is inherited and must be changed on the generic")


def _read_attribute_list(attribute: AttributeSchema, property_name: AttributeListProperty) -> JsonValue:
    match property_name:
        case AttributeListProperty.CHOICES:
            return to_jsonable_python(attribute.choices, serialize_as_any=True)
        case AttributeListProperty.ENUM:
            return to_jsonable_python(attribute.enum, serialize_as_any=True)
        case _:
            assert_never(property_name)


async def apply_attribute_property_change(
    *,
    kind: str,
    attribute: str,
    change: AttributeListChange,
    db: InfrahubDatabase,
    branch: Branch,
    account_id: str,
    service: InfrahubServices,
    context: InfrahubContext,
) -> None:
    """Apply `change` to the dropdown choices or the enum values of an attribute of the branch schema, and save it.

    The list is read and the change validated under the schema lock, so concurrent changes to one list all apply. The
    schema is saved with an applied schema change that holds the one operation, in the same transaction.

    Raises:
        ValidationError: The change does not apply to the attribute's current list.

    """
    candidate_builder = build_schema_candidate_builder()
    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        attribute_schema = branch_schema.get(name=kind, duplicate=False).get_attribute(name=attribute)
        previous_value = _read_attribute_list(attribute=attribute_schema, property_name=change.property_name)
        value = change.build_list(kind=kind, attribute=attribute_schema)
        operation = SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=kind,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name=attribute,
            property_name=change.property_name.value,
            value=to_jsonable_python(value, serialize_as_any=True),
            previous_value=previous_value,
        )
        candidate = candidate_builder.from_operations(
            branch_schema=branch_schema,
            operations=[operation],
            default_branch_schema=registry.schema.get_schema_branch(name=registry.default_branch),
        )
        diff = candidate.validation.diff

        if diff.all:
            log.info(f"Schema has diff, will need to be updated {diff.all}", branch=branch.name)
            at = Timestamp()
            async with db.start_transaction() as dbt:
                # The registry is replaced before the commit, so a failed record write must happen before it.
                recorder = build_schema_change_recorder(db=dbt, default_branch_name=registry.default_branch)
                await recorder.record_applied(branch=branch, operations=[operation], at=at, user_id=account_id)
                await registry.schema.update_schema_branch(
                    schema=candidate.schema,
                    db=dbt,
                    branch=branch.name,
                    limit=diff.all,
                    update_db=True,
                    at=at,
                    user_id=account_id,
                )
                branch.update_schema_hash()
                log.info("Schema has been updated", branch=branch.name, hash=branch.active_schema_hash.main)
                await branch.save(db=dbt, user_id=account_id)

            await service.component.refresh_schema_hash(branches=[branch.name])

            log_data = get_log_data()
            request_id = log_data.get("request_id", "")
            event = SchemaUpdatedEvent(
                branch_name=branch.name,
                schema_hash=branch.active_schema_hash.main,
                changed_elements=build_changed_elements_payload(diff),
                meta=EventMeta(
                    initiator_id=WORKER_IDENTITY,
                    request_id=request_id,
                    account_id=account_id,
                    branch=branch,
                    context=context.to_event_context(),
                ),
            )
            await service.event.send(event=event)
