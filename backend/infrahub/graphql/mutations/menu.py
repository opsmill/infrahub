from typing import TYPE_CHECKING, Any, Optional

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core.branch import Branch
from infrahub.core.constants import RESTRICTED_NAMESPACES
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext

EXTENDED_RESTRICTED_NAMESPACES = RESTRICTED_NAMESPACES + ["Builtin"]


def validate_namespace(data: InputObjectType) -> None:
    namespace = data.get("namespace")
    if isinstance(namespace, dict) and "value" in namespace:
        namespace_value = str(namespace.get("value"))
        if namespace_value in EXTENDED_RESTRICTED_NAMESPACES:
            raise ValidationError(
                input_value={"namespace": f"{namespace_value} is not valid, it's a restricted namespace"}
            )


class InfrahubCoreMenuMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls, schema: NodeSchema, _meta: Optional[Any] = None, **options: dict[str, Any]
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
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
        validate_namespace(data=data)

        obj, result = await super().mutate_create(info=info, data=data, branch=branch, at=at)

        return obj, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context

        obj = await NodeManager.find_object(
            db=context.db, kind=CoreMenuItem, id=data.get("id"), hfid=data.get("hfid"), branch=branch, at=at
        )
        validate_namespace(data=data)

        if obj.protected.value:
            raise ValidationError(input_value="This object is protected, it can't be modified.")

        obj, result = await super().mutate_update(info=info, data=data, branch=branch, at=at, node=obj)  # type: ignore[assignment]
        return obj, result  # type: ignore[return-value]

    @classmethod
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        obj = await NodeManager.find_object(
            db=context.db, kind=CoreMenuItem, id=data.get("id"), hfid=data.get("hfid"), branch=branch, at=at
        )
        if obj.protected.value:
            raise ValidationError(input_value="This object is protected, it can't be deleted.")

        return await super().mutate_delete(info=info, data=data, branch=branch, at=at)
