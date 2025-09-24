from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.database import retry_db_transaction
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class InfrahubDisplayLabelUpdateInput(InputObjectType):
    id = String(required=True)
    kind = String(required=True)
    value = String(required=True)


class UpdateDisplayLabel(Mutation):
    class Arguments:
        data = InfrahubDisplayLabelUpdateInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="update_computed_attribute")
    async def mutate(
        cls,
        _: dict,
        info: GraphQLResolveInfo,
        data: InfrahubDisplayLabelUpdateInput,
        context: ContextInput | None = None,
    ) -> UpdateDisplayLabel:
        graphql_context: GraphqlContext = info.context
        node_schema = registry.schema.get_node_schema(
            name=str(data.kind), branch=graphql_context.branch.name, duplicate=False
        )
        if not node_schema.display_label:
            raise ValidationError(input_value=f"{node_schema.kind}.display_label has not been defined for this kind")

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
                fields={"display_label": None},
            )
        ):
            raise NodeNotFoundError(
                node_type="target_node",
                identifier=str(data.id),
                message="The indicated node was not found in the database",
            )

        existing_label = target_node._display_label.value if target_node._display_label else None
        print(existing_label)

        # TODO: Add the proper code here and send the correct event to
        # indicate that the display_label was updated

        result: dict[str, Any] = {"ok": True}

        return cls(**result)
