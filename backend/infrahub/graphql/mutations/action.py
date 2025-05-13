from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from typing_extensions import Self

from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

log = get_logger()


class InfrahubTriggerRuleMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
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
        database: InfrahubDatabase | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        trigger_rule_definition, result = await super().mutate_create(info=info, data=data, branch=branch)

        return trigger_rule_definition, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        trigger_rule_definition, result = await super().mutate_update(info=info, data=data, branch=branch)

        return trigger_rule_definition, result
