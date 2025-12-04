from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from graphene import Boolean, InputObjectType, List, Mutation, NonNull, String

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.database import retry_db_transaction
from infrahub.events import EventMeta
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.log import get_log_data
from infrahub.permissions import define_global_permission_from_branch
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class InfrahubHFIDUpdateInput(InputObjectType):
    id = String(required=True)
    kind = String(required=True)
    value = List(NonNull(String), required=True)


class UpdateHFID(Mutation):
    class Arguments:
        data = InfrahubHFIDUpdateInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="update_hfid")
    async def mutate(
        cls,
        _: dict,
        info: GraphQLResolveInfo,
        data: InfrahubHFIDUpdateInput,
        context: ContextInput | None = None,
    ) -> UpdateHFID:
        graphql_context: GraphqlContext = info.context
        node_schema = registry.schema.get_node_schema(
            name=str(data.kind), branch=graphql_context.branch.name, duplicate=False
        )
        if node_schema.human_friendly_id is None:
            raise ValidationError(
                input_value=f"{node_schema.kind}.human_friendly_id has not been defined for this kind."
            )

        updated_hfid = cast("list[str]", data.value)

        if len(node_schema.human_friendly_id) != len(updated_hfid):
            raise ValidationError(
                input_value=f"{node_schema.kind}.human_friendly_id requires {len(node_schema.human_friendly_id)} parts data has {len(updated_hfid)}"
            )

        graphql_context.active_permissions.raise_for_permissions(
            permissions=[
                define_global_permission_from_branch(
                    permission=GlobalPermissions.UPDATE_OBJECT_HFID_DISPLAY_LABEL,
                    branch_name=graphql_context.branch.name,
                ),
                ObjectPermission(
                    namespace=node_schema.namespace,
                    name=node_schema.name,
                    action=PermissionAction.UPDATE.value,
                    decision=PermissionDecision.ALLOW_DEFAULT.value
                    if graphql_context.branch.name == registry.default_branch
                    else PermissionDecision.ALLOW_OTHER.value,
                ),
            ]
        )
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if not (
            target_node := await NodeManager.get_one(
                db=graphql_context.db,
                kind=node_schema.kind,
                id=str(data.id),
                branch=graphql_context.branch,
                fields={"human_friendly_id": None},
            )
        ):
            raise NodeNotFoundError(
                node_type=node_schema.kind,
                identifier=str(data.id),
                message="The targeted node was not found in the database",
            )

        existing = await target_node.get_hfid(db=graphql_context.db) if target_node.has_human_friendly_id() else None
        if updated_hfid != existing:
            await target_node.set_human_friendly_id(value=updated_hfid)

            async with graphql_context.db.start_transaction() as dbt:
                await target_node.save(db=dbt, fields=["human_friendly_id"])

            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            event = NodeUpdatedEvent(
                kind=node_schema.kind,
                node_id=target_node.get_id(),
                changelog=target_node.node_changelog,
                fields=["human_friendly_id"],
                meta=EventMeta(
                    context=graphql_context.get_context(),
                    initiator_id=WORKER_IDENTITY,
                    request_id=request_id,
                    account_id=graphql_context.active_account_session.account_id,
                    branch=graphql_context.branch,
                ),
            )
            await graphql_context.active_service.event.send(event=event)

        result: dict[str, Any] = {"ok": True}

        return cls(**result)
