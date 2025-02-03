from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import ComputedAttributeKind, MutationAction, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.database import retry_db_transaction
from infrahub.events import EventMeta, NodeMutatedEvent
from infrahub.exceptions import NodeNotFoundError, ValidationError
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

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="update_computed_attribute")
    async def mutate(
        cls,
        _: dict,
        info: GraphQLResolveInfo,
        data: InfrahubComputedAttributeUpdateInput,
    ) -> UpdateComputedAttribute:
        context: GraphqlContext = info.context
        node_schema = registry.schema.get_node_schema(name=str(data.kind), branch=context.branch.name, duplicate=False)
        target_attribute = node_schema.get_attribute(name=str(data.attribute))
        if (
            not target_attribute.computed_attribute
            or target_attribute.computed_attribute.kind == ComputedAttributeKind.USER
        ):
            raise ValidationError(input_value=f"{node_schema.kind}.{target_attribute.name} is not a computed attribute")

        context.active_permissions.raise_for_permission(
            permission=ObjectPermission(
                namespace=node_schema.namespace,
                name=node_schema.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value
                if context.branch.name == registry.default_branch
                else PermissionDecision.ALLOW_OTHER.value,
            )
        )

        if not (
            target_node := await NodeManager.get_one(
                db=context.db, kind=node_schema.kind, id=str(data.id), branch=context.branch
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
            async with context.db.start_transaction() as dbt:
                await target_node.save(db=dbt, fields=[str(data.attribute)])

            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            graphql_payload = await target_node.to_graphql(
                db=context.db, filter_sensitive=True, include_properties=False
            )

            event = NodeMutatedEvent(
                branch=context.branch.name,
                kind=node_schema.kind,
                node_id=target_node.get_id(),
                data=graphql_payload,
                fields=[str(data.attribute)],
                action=MutationAction.UPDATED,
                meta=EventMeta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            await context.active_service.event.send(event=event)

        result: dict[str, Any] = {"ok": True}

        return cls(**result)
