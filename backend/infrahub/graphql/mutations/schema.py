from typing import Dict, Union

from graphene import Boolean, Field, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RESTRICTED_NAMESPACES
from infrahub.core.manager import NodeManager
from infrahub.core.schema import DropdownChoice, GenericSchema, NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from ..types import DropdownFields

log = get_logger()


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

    ok = Boolean()
    object = Field(DropdownFields)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: SchemaDropdownAddInput,
    ):
        db: InfrahubDatabase = info.context.get("infrahub_database")
        branch: Branch = info.context.get("infrahub_branch")
        kind = registry.get_schema(name=str(data.kind), branch=branch.name)
        attribute = str(data.attribute)
        validate_kind_dropdown(kind=kind, attribute=attribute)
        dropdown = str(data.dropdown)
        choice = DropdownChoice(name=dropdown, color=data.color, label=data.label, description=data.description)

        if found_attribute := [attrib for attrib in kind.attributes if attrib.name == attribute]:
            attrib = found_attribute[0]
            if [dropdown_entry for dropdown_entry in attrib.choices if dropdown_entry.name == dropdown]:
                raise ValidationError(
                    f"The dropdown value {dropdown} already exists on {kind.kind} in attribute {attribute}"
                )
            attrib.choices.append(choice)

        await update_registry(kind=kind, branch=branch, db=db)

        kind = registry.get_schema(name=str(data.kind), branch=branch.name)
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

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: SchemaDropdownRemoveInput,
    ) -> Dict[str, bool]:
        db: InfrahubDatabase = info.context.get("infrahub_database")
        branch: Branch = info.context.get("infrahub_branch")
        kind = registry.get_schema(name=str(data.kind), branch=branch.name)

        attribute = str(data.attribute)
        validate_kind_dropdown(kind=kind, attribute=attribute)
        dropdown = str(data.dropdown)
        nodes_with_dropdown = await NodeManager.query(
            db=db, schema=kind.kind, filters={f"{attribute}__value": dropdown}
        )
        if nodes_with_dropdown:
            raise ValidationError(f"There are still {kind.kind} objects using this dropdown")

        if found_attribute := [attrib for attrib in kind.attributes if attrib.name == attribute]:
            attrib = found_attribute[0]
            if not [dropdown_entry for dropdown_entry in attrib.choices if dropdown_entry.name == dropdown]:
                raise ValidationError(
                    f"The dropdown value {dropdown} does not exists on {kind.kind} in attribute {attribute}"
                )
            if len(attrib.choices) == 1:
                raise ValidationError(f"Unable to remove the last dropdown on {kind.kind} in attribute {attribute}")
            attrib.choices = [entry for entry in attrib.choices if dropdown != entry.name]

        await update_registry(kind=kind, branch=branch, db=db)

        return {"ok": True}


class SchemaEnumAdd(Mutation):
    class Arguments:
        data = SchemaEnumInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: SchemaEnumInput,
    ) -> Dict[str, bool]:
        db: InfrahubDatabase = info.context.get("infrahub_database")
        branch: Branch = info.context.get("infrahub_branch")
        kind = registry.get_schema(name=str(data.kind), branch=branch.name)

        attribute = str(data.attribute)
        enum = str(data.enum)
        validate_kind_enum(kind=kind, attribute=attribute)

        for attrib in kind.attributes:
            if attribute == attrib.name:
                if enum in attrib.enum:
                    raise ValidationError(
                        f"The enum value {enum} already exists on {kind.kind} in attribute {attribute}"
                    )
                attrib.enum.append(enum)

        await update_registry(kind=kind, branch=branch, db=db)

        return {"ok": True}


class SchemaEnumRemove(Mutation):
    class Arguments:
        data = SchemaEnumInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: SchemaEnumInput,
    ) -> Dict[str, bool]:
        db: InfrahubDatabase = info.context.get("infrahub_database")
        branch: Branch = info.context.get("infrahub_branch")
        kind = registry.get_schema(name=str(data.kind), branch=branch.name)

        attribute = str(data.attribute)
        enum = str(data.enum)
        validate_kind_enum(kind=kind, attribute=attribute)
        nodes_with_enum = await NodeManager.query(db=db, schema=kind.kind, filters={f"{attribute}__value": enum})
        if nodes_with_enum:
            raise ValidationError(f"There are still {kind.kind} objects using this enum")

        for attrib in kind.attributes:
            if attribute == attrib.name:
                if enum not in attrib.enum:
                    raise ValidationError(
                        f"The enum value {enum} does not exists on {kind.kind} in attribute {attribute}"
                    )
                if len(attrib.enum) == 1:
                    raise ValidationError(f"Unable to remove the last enum on {kind.kind} in attribute {attribute}")
                attrib.enum = [entry for entry in attrib.enum if entry != enum]

        await update_registry(kind=kind, branch=branch, db=db)

        return {"ok": True}


def validate_kind_dropdown(kind: Union[GenericSchema, NodeSchema], attribute: str) -> None:
    validate_kind(kind=kind, attribute=attribute)
    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]
    if matching_attribute and matching_attribute[0].kind != "Dropdown":
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is not a Dropdown")


def validate_kind_enum(kind: Union[GenericSchema, NodeSchema], attribute: str) -> None:
    validate_kind(kind=kind, attribute=attribute)
    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]
    if not matching_attribute[0].enum:
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is not an enum")


def validate_kind(kind: Union[GenericSchema, NodeSchema], attribute: str) -> None:
    if kind.namespace in RESTRICTED_NAMESPACES:
        raise ValidationError(f"Operation not allowed for {kind.kind} in restricted namespace {kind.namespace}")
    if attribute not in kind.attribute_names:
        raise ValidationError(f"Attribute {attribute} does not exist on {kind.kind}")

    matching_attribute = [attrib for attrib in kind.attributes if attrib.name == attribute]

    if matching_attribute[0].inherited:
        raise ValidationError(f"Attribute {attribute} on {kind.kind} is inherited and must be changed on the generic")


async def update_registry(kind: NodeSchema, branch: Branch, db: InfrahubDatabase) -> None:
    async with lock.registry.global_schema_lock():
        branch_schema = registry.schema.get_schema_branch(name=branch.name)

        # We create a copy of the existing branch schema to do some validation before loading it.
        tmp_schema = branch_schema.duplicate()

        tmp_schema.set(name=kind.kind, schema=kind)
        tmp_schema.process()

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
                await services.send(message)
