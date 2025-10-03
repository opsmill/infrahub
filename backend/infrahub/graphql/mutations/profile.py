from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from opentelemetry import trace
from typing_extensions import Self

from infrahub.core.manager import NodeManager
from infrahub.core.schema import ProfileSchema
from infrahub.graphql.types.context import ContextInput
from infrahub.log import get_logger
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow

log = get_logger()


class InfrahubProfileMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: ProfileSchema,
        _meta: InfrahubMutationOptions | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, ProfileSchema):
            raise ValueError(f"You need to pass a valid ProfileSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def _send_profile_refresh_workflows(
        cls,
        db: InfrahubDatabase,
        workflow_service: InfrahubWorkflow,
        branch_name: str,
        obj: Node,
        node_ids: list[str] | None = None,
    ) -> None:
        if not node_ids:
            related_nodes = await obj.related_nodes.get_relationships(db=db)  # type: ignore[attr-defined]
            node_ids = [rel.peer_id for rel in related_nodes]
        if node_ids:
            await workflow_service.submit_workflow(
                workflow=PROFILE_REFRESH_MULTIPLE,
                parameters={
                    "branch_name": branch_name,
                    "node_ids": node_ids,
                },
            )

    @classmethod
    def _get_profile_attr_values_map(cls, obj: Node) -> dict[str, Any]:
        attr_values_map = {}
        for attr_schema in obj.get_schema().attributes:
            # profile name update can be ignored
            if attr_schema.name == "profile_name":
                continue
            attr_values_map[attr_schema.name] = getattr(obj, attr_schema.name).value
        return attr_values_map

    @classmethod
    async def _get_profile_related_node_ids(cls, db: InfrahubDatabase, obj: Node) -> set[str]:
        related_nodes = await obj.related_nodes.get_relationships(db=db)  # type: ignore[attr-defined]
        if related_nodes:
            related_node_ids = {rel.peer_id for rel in related_nodes}
        else:
            related_node_ids = set()
        return related_node_ids

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
        workflow_service = graphql_context.active_service.workflow

        obj, mutation = await super().mutate_create(
            info=info, data=data, branch=branch, database=database, override_data=override_data
        )
        await cls._send_profile_refresh_workflows(
            db=db, workflow_service=workflow_service, branch_name=branch.name, obj=obj
        )

        return obj, mutation

    @classmethod
    async def _call_mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> tuple[Node, Self]:
        workflow_service = info.context.active_service.workflow
        original_attr_values = cls._get_profile_attr_values_map(obj=obj)
        original_related_node_ids = await cls._get_profile_related_node_ids(db=db, obj=obj)

        obj, mutation = await super()._call_mutate_update(
            info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
        )

        updated_attr_values = cls._get_profile_attr_values_map(obj=obj)
        updated_related_node_ids = await cls._get_profile_related_node_ids(db=db, obj=obj)

        if original_attr_values != updated_attr_values:
            await cls._send_profile_refresh_workflows(
                db=db, workflow_service=workflow_service, branch_name=branch.name, obj=obj
            )
        elif updated_related_node_ids != original_related_node_ids:
            removed_node_ids = original_related_node_ids - updated_related_node_ids
            added_node_ids = updated_related_node_ids - original_related_node_ids
            await cls._send_profile_refresh_workflows(
                db=db,
                workflow_service=workflow_service,
                branch_name=branch.name,
                obj=obj,
                node_ids=list(removed_node_ids) + list(added_node_ids),
            )

        return obj, mutation

    @classmethod
    async def _delete_obj(cls, graphql_context: GraphqlContext, branch: Branch, obj: Node) -> list[Node]:
        db = graphql_context.db
        workflow_service = graphql_context.active_service.workflow
        related_node_ids = await cls._get_profile_related_node_ids(db=db, obj=obj)
        deleted = await super()._delete_obj(graphql_context=graphql_context, branch=branch, obj=obj)
        await cls._send_profile_refresh_workflows(
            db=db, workflow_service=workflow_service, branch_name=branch.name, obj=obj, node_ids=list(related_node_ids)
        )
        return deleted


class ProfilesRefreshInput(InputObjectType):
    id = String(required=False)


class InfrahubProfilesRefresh(Mutation):
    class Arguments:
        data = ProfilesRefreshInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @trace.get_tracer(__name__).start_as_current_span("profiles_refresh")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ProfilesRefreshInput,
        context: ContextInput | None = None,  # noqa: ARG003
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        db = graphql_context.db
        branch = graphql_context.branch
        obj = await NodeManager.get_one(
            db=db,
            branch=branch,
            id=str(data.id),
            include_source=True,
        )
        node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
        updated_fields = await node_profiles_applier.apply_profiles(node=obj)
        if updated_fields:
            await obj.save(db=db, fields=updated_fields)

        return cls(ok=True)
