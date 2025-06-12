from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from graphene import InputObjectType, Mutation
from typing_extensions import Self

from infrahub.core.protocols import CoreNodeTriggerAttributeMatch, CoreNodeTriggerRelationshipMatch, CoreNodeTriggerRule
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase

    from ..initialization import GraphqlContext

log = get_logger()


class InfrahubTriggerRuleMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
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
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        _validate_node_kind(data=data, db=db)
        trigger_rule_definition, result = await super().mutate_create(info=info, data=data, branch=branch, database=db)

        return trigger_rule_definition, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        node: Node | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        _validate_node_kind(data=data, db=db)
        trigger_rule_definition, result = await super().mutate_update(info=info, data=data, branch=branch, database=db)

        return trigger_rule_definition, result


class InfrahubTriggerRuleMatchMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
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
        database: InfrahubDatabase | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        async with graphql_context.db.start_transaction() as dbt:
            trigger_match, result = await super().mutate_create(info=info, data=data, branch=branch, database=dbt)
            trigger_match_model = cast(CoreNodeTriggerAttributeMatch | CoreNodeTriggerRelationshipMatch, trigger_match)
            node_trigger_rule = await trigger_match_model.trigger.get_peer(db=dbt, raise_on_error=True)
            node_trigger_rule_model = cast(CoreNodeTriggerRule, node_trigger_rule)
            node_schema = dbt.schema.get_node_schema(name=node_trigger_rule_model.node_kind.value, duplicate=False)
            _validate_node_kind_field(data=data, node_schema=node_schema)

        return trigger_match, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        async with graphql_context.db.start_transaction() as dbt:
            trigger_match, result = await super().mutate_update(info=info, data=data, branch=branch, database=dbt)
            trigger_match_model = cast(CoreNodeTriggerAttributeMatch | CoreNodeTriggerRelationshipMatch, trigger_match)
            node_trigger_rule = await trigger_match_model.trigger.get_peer(db=dbt, raise_on_error=True)
            node_trigger_rule_model = cast(CoreNodeTriggerRule, node_trigger_rule)
            node_schema = dbt.schema.get_node_schema(name=node_trigger_rule_model.node_kind.value, duplicate=False)
            _validate_node_kind_field(data=data, node_schema=node_schema)

        return trigger_match, result


def _validate_node_kind(data: InputObjectType, db: InfrahubDatabase) -> None:
    input_data = cast(dict[str, dict[str, Any]], data)
    if node_kind := input_data.get("node_kind"):
        value = node_kind.get("value")
        if isinstance(value, str):
            try:
                db.schema.get_node_schema(name=value, duplicate=False)
            except SchemaNotFoundError as exc:
                raise ValidationError(
                    input_value={"node_kind": "The requested node_kind schema was not found"}
                ) from exc
            except ValueError as exc:
                raise ValidationError(input_value={"node_kind": "The requested node_kind is not a valid node"}) from exc


def _validate_node_kind_field(data: InputObjectType, node_schema: NodeSchema) -> None:
    input_data = cast(dict[str, dict[str, Any]], data)
    if attribute_name := input_data.get("attribute_name"):
        value = attribute_name.get("value")
        if isinstance(value, str):
            if value not in node_schema.attribute_names:
                raise ValidationError(
                    input_value={
                        "attribute_name": f"The attribute {value} doesn't exist on related node trigger using {node_schema.kind}"
                    }
                )
    if relationship_name := input_data.get("relationship_name"):
        value = relationship_name.get("value")
        if isinstance(value, str):
            if value not in node_schema.relationship_names:
                raise ValidationError(
                    input_value={
                        "relationship_name": f"The relationship {value} doesn't exist on related node trigger using {node_schema.kind}"
                    }
                )
