from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import ComputedAttributeKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.database import retry_db_transaction
from infrahub.events import EventMeta
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.log import get_log_data
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class InfrahubComputedAttributeUpdateInput(InputObjectType):
    id = String(required=True)
    kind = String(required=True)
    attribute = String(required=True)
    value = String(required=True)


class UpdateComputedAttribute(Mutation):
    class Arguments:
        data = InfrahubComputedAttributeUpdateInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="update_computed_attribute")
    async def mutate(
        cls,
        _: dict,
        info: GraphQLResolveInfo,
        data: InfrahubComputedAttributeUpdateInput,
        context: ContextInput | None = None,
    ) -> UpdateComputedAttribute:
        graphql_context: GraphqlContext = info.context
        node_schema = registry.schema.get_node_schema(
            name=str(data.kind), branch=graphql_context.branch.name, duplicate=False
        )
        target_attribute = node_schema.get_attribute(name=str(data.attribute))
        if (
            not target_attribute.computed_attribute
            or target_attribute.computed_attribute.kind == ComputedAttributeKind.USER
        ):
            raise ValidationError(input_value=f"{node_schema.kind}.{target_attribute.name} is not a computed attribute")

        graphql_context.active_permissions.raise_for_permission(
            permission=ObjectPermission(
                namespace=node_schema.namespace,
                name=node_schema.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value
                if graphql_context.branch.name == registry.default_branch
                else PermissionDecision.ALLOW_OTHER.value,
            )
        )
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if not (
            target_node := await NodeManager.get_one(
                db=graphql_context.db,
                kind=node_schema.kind,
                id=str(data.id),
                branch=graphql_context.branch,
                fields={target_attribute.name: None},
            )
        ):
            raise NodeNotFoundError(
                node_type="target_node",
                identifier=str(data.id),
                message="The indicated node was not found in the database",
            )

        attribute_field = getattr(target_node, str(data.attribute), None)
        if not attribute_field:
            raise NodeNotFoundError(
                node_type="target_node",
                identifier=str(data.id),
                message="The indicated not does not have the specified attribute_name",
            )
        if attribute_field.value != str(data.value):
            attribute_field.value = str(data.value)
            async with graphql_context.db.start_transaction() as dbt:
                await target_node.save(db=dbt, fields=[str(data.attribute)])

            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            event = NodeUpdatedEvent(
                kind=node_schema.kind,
                node_id=target_node.get_id(),
                changelog=target_node.node_changelog.model_dump(),
                fields=[str(data.attribute)],
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
