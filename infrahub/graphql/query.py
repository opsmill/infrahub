from graphene import Boolean, DateTime, Field, Int, List, ObjectType, String
from graphene.types.generic import GenericScalar
from graphene.types.objecttype import ObjectTypeOptions

import infrahub.config as config
from infrahub.core import get_branch
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema

# pylint: disable=too-few-public-methods

DEFAULT_BRANCH = "main"


# ------------------------------------------
# Old Infrahub GraphQLType
# ------------------------------------------
class InfrahubObjectTypeOptions(ObjectTypeOptions):
    model = None


class InfrahubObjectType(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        model=None,
        interfaces=(),
        # possible_types=(),
        # default_resolver=None,
        _meta=None,
        **options,
    ):

        # Make sure model is a valid Infrahub Node Class
        # if not is_mapped_class(model):
        #     raise ValueError(
        #         "You need to pass a valid SQLAlchemy Model in " '{}.Meta, received "{}".'.format(cls.__name__, model)
        #     )

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
# New Infrahub GraphQLType
# ------------------------------------------
class InfrahubObjectOptions(ObjectTypeOptions):
    schema = None


class InfrahubObject(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, interfaces=(), _meta=None, **options):

        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)

    @classmethod
    async def get_list(cls, fields: dict, context: dict, *args, **kwargs):

        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:

            context["infrahub_session"] = session

            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            if filters:
                objs = await NodeManager.query(
                    session=session,
                    schema=cls._meta.schema,
                    filters=filters,
                    fields=fields,
                    at=at,
                    branch=branch,
                    account=account,
                    include_source=True,
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
                )

            if not objs:
                return []

            return [await obj.to_graphql(session=session, fields=fields) for obj in objs]


# ------------------------------------------
#
# ------------------------------------------
class BaseAttribute(ObjectType):
    id = Field(String)
    is_inherited = Field(Boolean)
    is_protected = Field(Boolean)
    is_visible = Field(Boolean)
    updated_at = Field(DateTime)
    source = Field("infrahub.graphql.query.AccountType")


class StrAttributeType(BaseAttribute):
    value = Field(String)

    class Meta:
        description = "Attribute of type String"
        name = "StrAttribute"


class IntAttributeType(BaseAttribute):
    value = Field(Int)

    class Meta:
        description = "Attribute of type Integer"
        name = "IntAttribute"


class BoolAttributeType(BaseAttribute):
    value = Field(Boolean)

    class Meta:
        description = "Attribute of type Boolean"
        name = "BoolAttribute"


class AnyAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type GenericScalar"
        name = "AnyAttribute"


class AccountType(InfrahubObjectType):
    id = String(required=True)
    name = Field(StrAttributeType, required=True)
    description = Field(StrAttributeType, required=False)


# ------------------------------------------
#
# ------------------------------------------
class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    is_data_only = Boolean(required=False)
    is_default = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(cls, fields: dict, context: dict, *args, **kwargs):

        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:

            context["infrahub_session"] = session

            # at, branch = extract_global_kwargs(kwargs)
            objs = await Branch.get_list(session=session)

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs]


class BranchDiffNodeAttributeType(ObjectType):
    attr_name = String()
    attr_uuid = String()
    changed_at = String()
    action = String()


class BranchDiffNodeType(ObjectType):
    branch = String()
    node_labels = List(String)
    node_uuid = String()
    changed_at = String()
    action = String()
    attributes = List(BranchDiffNodeAttributeType)


class BranchDiffAttributeType(ObjectType):
    branch = String()
    node_labels = List(String)
    node_uuid = String()
    attr_name = String()
    attr_uuid = String()
    changed_at = String()
    action = String()


class BranchDiffRelationshipType(ObjectType):
    branch = String()
    source_node_labels = List(String)
    source_node_uuid = String()
    dest_node_labels = List(String)
    dest_node_uuid = String()
    rel_uuid = String()
    rel_name = String()
    changed_at = String()
    action = String()


class BranchDiffFileType(ObjectType):
    branch = String()
    repository_name = String()
    repository_uuid = String()
    files = List(String)


class BranchDiffType(ObjectType):
    nodes = List(BranchDiffNodeType)
    files = List(BranchDiffFileType)
    attributes = List(BranchDiffAttributeType)
    relationships = List(BranchDiffRelationshipType)

    @classmethod
    async def get_diff(cls, branch, fields: dict, context: dict, *args, **kwargs):

        session = context.get("infrahub_session")
        branch = await get_branch(branch=branch, session=session)
        # diff = await branch.diff()

        # FIXME need to refactor this method to account to the new diff format
        return {}
        # return {
        #     "nodes": [dataclasses.asdict(item) for item in diff.get_nodes()] if "nodes" in fields else None,
        #     "files": diff.get_files() if "files" in fields else None,
        #     "attributes": [dataclasses.asdict(item) for item in diff.get_attributes()]
        #     if "attributes" in fields
        #     else None,
        #     "relationships": [dataclasses.asdict(item) for item in diff.get_relationships()]
        #     if "relationships" in fields
        #     else None,
        # }
