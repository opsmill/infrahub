from __future__ import annotations

from graphene import (
    Boolean,
    DateTime,
    Field,
    InputObjectType,
    Int,
    Interface,
    List,
    ObjectType,
    String,
    Union,
)
from graphene.types.generic import GenericScalar
from graphene.types.interface import InterfaceOptions
from graphene.types.objecttype import ObjectTypeOptions
from graphene.types.union import UnionOptions

import infrahub.config as config
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema import GroupSchema, NodeSchema

# -------------------------------------------------------
# Various Mixins
# -------------------------------------------------------


class GetListMixin:
    """Mixins to Query the list of nodes using the NodeManager."""

    @classmethod
    async def get_list(cls, fields: dict, context: dict, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            filter_ids = kwargs.get("ids")

            if filter_ids:
                objs = await NodeManager.get_many(
                    session=session,
                    ids=filter_ids,
                    fields=fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )
                objs = objs.values()
            elif filters:
                objs = await NodeManager.query(
                    session=session,
                    schema=cls._meta.schema,
                    filters=filters,
                    fields=fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )
            else:
                objs = await NodeManager.query(
                    session=session,
                    schema=cls._meta.schema,
                    fields=fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )

            if not objs:
                return []

            return [await obj.to_graphql(session=session, fields=fields) for obj in objs]

    @classmethod
    async def get_paginated_list(cls, fields: dict, context: dict, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")
        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            count = 0
            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            filter_ids = kwargs.get("ids")
            node_fields = fields["edges"]["node"]
            if filter_ids:
                objs = await NodeManager.get_many(
                    session=session,
                    ids=filter_ids,
                    fields=node_fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )
                objs = objs.values()
            elif filters:
                objs = await NodeManager.query(
                    session=session,
                    schema=cls._meta.schema,
                    filters=filters,
                    fields=node_fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )
            else:
                objs = await NodeManager.query(
                    session=session,
                    schema=cls._meta.schema,
                    fields=node_fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
                    include_owner=True,
                )
            if not objs:
                return []
            objects = [{"node": await obj.to_graphql(session=session, fields=node_fields)} for obj in objs]
            response = {"count": count, "edges": objects}
            return response


# -------------------------------------------------------
# GraphQL Union Type Object
# -------------------------------------------------------
class InfrahubUnionOptions(UnionOptions):
    schema = None


class InfrahubUnion(Union):
    class Meta:
        """We must provide a placeholder types because __init_subclass__ is defined at the parent level
        and it will automatically check if there is at least one type defined when the class is loaded."""

        types = ("PlaceHolder",)

    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: GroupSchema = None, types=(), _meta=None, **options
    ):  # pylint: disable=arguments-renamed
        if not isinstance(schema, GroupSchema):
            raise ValueError(f"You need to pass a valid GroupSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubUnionOptions(cls)

        _meta.schema = schema
        _meta.types = types

        super(Union, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def resolve_type(cls, instance, info):
        branch = info.context["infrahub_branch"]

        if "type" in instance:
            return registry.get_graphql_type(name=f"Related{instance['type']}", branch=branch)

        raise ValueError("Unable to identify the type of the instance.")


# -------------------------------------------------------
# GraphQL Interface Type Object
# -------------------------------------------------------


class InfrahubInterfaceOptions(InterfaceOptions):
    schema = None


class InfrahubInterface(Interface, GetListMixin):
    @classmethod
    def resolve_type(cls, instance, info):
        branch = info.context["infrahub_branch"]

        if "Related" in cls.__name__ and "type" in instance:
            return registry.get_graphql_type(name=f"Related{instance['type']}", branch=branch)

        if "type" in instance:
            return registry.get_graphql_type(name=instance["type"], branch=branch)

        raise ValueError("Unable to identify the type of the instance.")


# -------------------------------------------------------
# GraphQL Object Types for the default Node object,
#   uses the NodeManager to query all members
# -------------------------------------------------------


class InfrahubObjectOptions(ObjectTypeOptions):
    schema = None


class InfrahubObject(ObjectType, GetListMixin):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema = None, interfaces=(), _meta=None, **options
    ):  # pylint: disable=arguments-differ
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)


# -------------------------------------------------------
# GraphQL Object Types for the StandardNode object like Branch
# -------------------------------------------------------
class InfrahubObjectTypeOptions(ObjectTypeOptions):
    model = None


class InfrahubObjectType(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        model=None,
        interfaces=(),
        # possible_types=(),
        # default_resolver=None,
        _meta=None,
        **options,
    ):
        if not _meta:
            _meta = InfrahubObjectTypeOptions(cls)

        _meta.model = model

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)

    @classmethod
    async def get_list(cls, fields, context, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            if filters:
                objs = await cls._meta.model.get_list(
                    filters=filters, at=at, branch=branch, account=account, include_source=True, session=session
                )
            else:
                objs = await cls._meta.model.get_list(
                    at=at, branch=branch, account=account, include_source=True, session=session
                )

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs]


# ------------------------------------------
# Attributes and Related Object related Types
# ------------------------------------------


class RelatedNodeInput(InputObjectType):
    id = String(required=True)
    _relation__is_visible = Boolean(required=False)
    _relation__is_protected = Boolean(required=False)
    _relation__owner = String(required=False)
    _relation__source = String(required=False)


class RelatedNodeInterface(InfrahubInterface):
    _relation__updated_at = DateTime(required=False)
    _relation__is_visible = Boolean(required=False)
    _relation__is_protected = Boolean(required=False)
    # Since _relation__owner and _relation__source are using a Type that is generated dynamically
    # these 2 fields will be dynamically inserted when we generate the GraphQL Schema
    # _relation__owner = Field("DataOwner", required=False)
    # _relation__source = Field("DataSource", required=False)


class AttributeInterface(InfrahubInterface):
    is_inherited = Field(Boolean)
    is_protected = Field(Boolean)
    is_visible = Field(Boolean)
    updated_at = Field(DateTime)
    # Since source and owner are using a Type that is generated dynamically
    # these 2 fields will be dynamically inserted when we generate the GraphQL Schema
    # source = Field("DataSource")
    # owner = Field("DataOwner")


class BaseAttribute(ObjectType):
    id = Field(String)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry.default_graphql_type[cls.__name__] = cls


class TextAttributeType(BaseAttribute):
    value = Field(String)

    class Meta:
        description = "Attribute of type Text"
        name = "TextAttribute"
        interfaces = {AttributeInterface}


class NumberAttributeType(BaseAttribute):
    value = Field(Int)

    class Meta:
        description = "Attribute of type Number"
        name = "NumberAttribute"
        interfaces = {AttributeInterface}


class CheckboxAttributeType(BaseAttribute):
    value = Field(Boolean)

    class Meta:
        description = "Attribute of type Checkbox"
        name = "CheckboxAttribute"
        interfaces = {AttributeInterface}


class StrAttributeType(BaseAttribute):
    value = Field(String)

    class Meta:
        description = "Attribute of type String"
        name = "StrAttribute"
        interfaces = {AttributeInterface}


class IntAttributeType(BaseAttribute):
    value = Field(Int)

    class Meta:
        description = "Attribute of type Integer"
        name = "IntAttribute"
        interfaces = {AttributeInterface}


class BoolAttributeType(BaseAttribute):
    value = Field(Boolean)

    class Meta:
        description = "Attribute of type Boolean"
        name = "BoolAttribute"
        interfaces = {AttributeInterface}


class ListAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type List"
        name = "ListAttribute"
        interfaces = {AttributeInterface}


class AnyAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type GenericScalar"
        name = "AnyAttribute"
        interfaces = {AttributeInterface}


# ------------------------------------------
# GraphQL Types related to the management of the Branch
# ------------------------------------------
class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    created_at = String(required=False)
    is_data_only = Boolean(required=False)
    is_default = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(cls, fields: dict, context: dict, *args, **kwargs):  # pylint: disable=unused-argument
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            objs = await Branch.get_list(session=session, **kwargs)

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs]


class BranchDiffPropertyValueType(ObjectType):
    new = GenericScalar()
    previous = GenericScalar()


class BranchDiffPropertyType(ObjectType):
    branch = String()
    type = String()
    changed_at = String()
    action = String()
    value = Field(BranchDiffPropertyValueType)


class BranchDiffAttributeType(ObjectType):
    name = String()
    id = String()
    changed_at = String()
    action = String()
    properties = List(BranchDiffPropertyType)


class BranchDiffNodeType(ObjectType):
    branch = String()
    kind = String()
    id = String()
    changed_at = String()
    action = String()
    attributes = List(BranchDiffAttributeType)


class BranchDiffRelationshipEdgeNodeType(ObjectType):
    id = String()
    kind = String()


class BranchDiffRelationshipType(ObjectType):
    branch = String()
    id = String()
    name = String()
    nodes = List(BranchDiffRelationshipEdgeNodeType)
    properties = List(BranchDiffPropertyType)
    changed_at = String()
    action = String()


class BranchDiffFileType(ObjectType):
    branch = String()
    repository = String()
    location = String()
    action = String()


class BranchDiffType(ObjectType):
    nodes = List(BranchDiffNodeType)
    files = List(BranchDiffFileType)
    relationships = List(BranchDiffRelationshipType)

    @classmethod
    async def get_diff(
        cls, branch, diff_from: str, diff_to: str, branch_only: bool, fields: dict, context: dict, *args, **kwargs
    ):  # pylint: disable=unused-argument
        context.get("infrahub_at")
        session = context.get("infrahub_session")
        rpc_client = context.get("infrahub_rpc_client")

        branch = await get_branch(branch=branch, session=session)

        diff = await branch.diff(session=session, diff_from=diff_from, diff_to=diff_to, branch_only=branch_only)

        response = {
            "nodes": [],
            "files": [],
            "relationships": [],
        }
        if "nodes" in fields:
            nodes = await diff.get_nodes(session=session)
            for items in nodes.values():
                for item in items.values():
                    response["nodes"].append(item.to_graphql())

        if "relationships" in fields:
            rels = await diff.get_relationships(session=session)

            for items in rels.values():
                for item in items.values():
                    for sub_item in item.values():
                        response["relationships"].append(sub_item.to_graphql())

        if "files" in fields:
            files = await diff.get_files(rpc_client=rpc_client, session=session)
            for items in files.values():
                for item in items:
                    response["files"].append(item.to_graphql())

        return response
