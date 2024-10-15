from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.constants import AttributeAssignmentType
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.database import retry_db_transaction
from infrahub.exceptions import NodeNotFoundError, ValidationError

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
        if target_attribute.assignment_type == AttributeAssignmentType.USER:
            raise ValidationError(input_value=f"{node_schema.kind}.{target_attribute.name} is not a computed attribute")

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

        attribute_field.value = str(data.value)
        await target_node.save(db=context.db)

        result: dict[str, Any] = {"ok": True}

        return cls(**result)
