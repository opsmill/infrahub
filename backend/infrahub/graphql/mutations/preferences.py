from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from graphene import InputObjectType, Mutation

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import PermissionDeniedError, ValidationError

from .main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions, UpsertResult

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.file_processor import FileUploadProcessor
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from ..initialization import GraphqlContext
    from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter

OWNERSHIP_DENIED_MESSAGE = "You are not allowed to manage the preferences of another account"


class InfrahubUserPreferenceMutation(InfrahubMutationMixin, Mutation):
    """Owner-scoped mutations for CoreUserPreference.

    Mirrors the AccountToken mechanism: writes re-check that the target row belongs to the
    calling account; accounts passing the admin checks (super admin) bypass the ownership check.
    Generic reads stay unfiltered in V1; enforcement is mutation-only.
    """

    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema, _meta: InfrahubMutationOptions | None = None, **options: dict[str, Any]
    ) -> None:
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def _is_admin(cls, graphql_context: GraphqlContext) -> bool:
        return graphql_context.permissions is not None and graphql_context.permissions.is_super_admin()

    @classmethod
    def _validate_account_input(cls, graphql_context: GraphqlContext, data: InputObjectType) -> None:
        """Ensure the account targeted by the mutation payload is the calling account.

        Raises:
            PermissionDeniedError: When the payload targets the preferences of another account.

        """
        if not graphql_context.account_session:
            raise PermissionDeniedError(message=OWNERSHIP_DENIED_MESSAGE)

        account_data = data.get("account")
        if account_data is None:
            # The relationship is mandatory at creation; on update an absent value means unchanged.
            return

        account_id = account_data.get("id")
        if account_id != graphql_context.account_session.account_id:
            raise PermissionDeniedError(message=OWNERSHIP_DENIED_MESSAGE)

    @classmethod
    async def _validate_row_owner(cls, graphql_context: GraphqlContext, obj: Node) -> None:
        """Ensure the existing row belongs to the calling account.

        Raises:
            PermissionDeniedError: When the row belongs to another account.

        """
        if not graphql_context.account_session:
            raise PermissionDeniedError(message=OWNERSHIP_DENIED_MESSAGE)

        owner = await obj.account.get_peer(db=graphql_context.db)  # type: ignore[attr-defined]
        if owner is None or owner.id != graphql_context.account_session.account_id:
            raise PermissionDeniedError(message=OWNERSHIP_DENIED_MESSAGE)

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        if not cls._is_admin(graphql_context):
            cls._validate_account_input(graphql_context=graphql_context, data=data)

        return await super().mutate_create(
            info=info, data=data, branch=branch, database=database, override_data=override_data
        )

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        node: Node | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        obj = node or await NodeManager.find_object(
            db=db, kind=cls._meta.active_schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch
        )

        if not cls._is_admin(graphql_context):
            await cls._validate_row_owner(graphql_context=graphql_context, obj=obj)
            cls._validate_account_input(graphql_context=graphql_context, data=data)

        return await super().mutate_update(info=info, data=data, branch=branch, database=database, node=obj)

    @classmethod
    async def _resolve_existing_node(
        cls,
        db: InfrahubDatabase,
        data: InputObjectType,
        branch: Branch,
        node_getter_default_filter: MutationNodeGetterByDefaultFilter,
        graphql_context: GraphqlContext,
    ) -> Node | None:
        """Resolve the existing node an upsert payload targets, mirroring the base-class resolution order.

        On top of the base-class lookups (id, default_filter, hfid), the id-less "lazy" payload is
        resolved to the target account's existing row: the uniqueness constraint on the `account`
        relationship does not yield an hfid, so without this lookup the base class would always take
        the create path and the second id-less upsert would fail on the uniqueness violation.
        """
        schema = cls._meta.active_schema
        if "id" in data:
            return await NodeManager.get_one(
                db=db, id=data["id"], kind=schema.kind, branch=branch, raise_on_error=True
            )

        node: Node | None = None
        if not schema.human_friendly_id and schema.default_filter is not None:
            node = await node_getter_default_filter.get_node(node_schema=schema, data=data, branch=branch)
        if "hfid" in data:
            node = await NodeManager.get_one_by_hfid(db=db, hfid=dict(data)["hfid"], kind=schema.kind, branch=branch)
        if node is not None:
            return node

        account_data = data.get("account")
        if account_data is not None:
            # Only an id peer spec is resolvable here; other specs (hfid) are rejected later
            # by _validate_account_input for non-admin callers.
            target_account_id = account_data.get("id")
        elif graphql_context.account_session:
            target_account_id = graphql_context.account_session.account_id
        else:
            target_account_id = None

        if target_account_id is None:
            return None

        results = await NodeManager.query(
            db=db, schema=schema.kind, filters={"account__ids": [target_account_id]}, branch=branch, limit=1
        )
        return results[0] if results else None

    @classmethod
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        node_getter_default_filter: MutationNodeGetterByDefaultFilter,
        database: InfrahubDatabase | None = None,
        file_processor: FileUploadProcessor | None = None,
    ) -> UpsertResult:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        # Resolve first, then validate: whatever node this upsert would update must pass the
        # ownership check before any write, regardless of how it was identified (id, hfid,
        # default_filter or the lazy account lookup).
        node = await cls._resolve_existing_node(
            db=db,
            data=data,
            branch=branch,
            node_getter_default_filter=node_getter_default_filter,
            graphql_context=graphql_context,
        )

        if not cls._is_admin(graphql_context):
            if node is not None:
                await cls._validate_row_owner(graphql_context=graphql_context, obj=node)
            cls._validate_account_input(graphql_context=graphql_context, data=data)

        if node is not None:
            file_stored = await cls._process_file(file_processor=file_processor, data=data, node=node)
            updated_obj, mutation = await cls._call_mutate_update(info=info, data=data, db=db, branch=branch, obj=node)
            return UpsertResult(node=updated_obj, mutation=mutation, created=False, file_stored=file_stored)

        # No existing row: the base class takes the create path, which re-applies the
        # ownership checks through our mutate_create override.
        return await super().mutate_upsert(
            info=info,
            data=data,
            branch=branch,
            node_getter_default_filter=node_getter_default_filter,
            database=database,
            file_processor=file_processor,
        )

    @classmethod
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        graphql_context: GraphqlContext = info.context

        obj = await NodeManager.find_object(
            db=graphql_context.db,
            kind=cls._meta.active_schema.kind,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=branch,
        )

        if not cls._is_admin(graphql_context):
            await cls._validate_row_owner(graphql_context=graphql_context, obj=obj)

        return await super().mutate_delete(info=info, data=data, branch=branch)


class InfrahubGlobalPreferenceMutation(InfrahubMutationMixin, Mutation):
    """Mutations for CoreGlobalPreference enforcing the 0..1 singleton invariant.

    The write permission itself (manage_global_preferences) is enforced by
    GlobalPreferenceManagerPermissionChecker; this class only refuses a second row.
    """

    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema, _meta: InfrahubMutationOptions | None = None, **options: dict[str, Any]
    ) -> None:
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        existing = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE, branch=branch, limit=1)
        if existing:
            raise ValidationError(
                input_value=(
                    f"{InfrahubKind.GLOBALPREFERENCE} is a singleton and a row already exists, update it instead"
                )
            )

        return await super().mutate_create(
            info=info, data=data, branch=branch, database=database, override_data=override_data
        )
