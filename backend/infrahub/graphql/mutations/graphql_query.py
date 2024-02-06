from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.mutations.main import InfrahubMutationMixin

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext


class InfrahubGraphQLQueryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
        **options: Dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def extract_query_info(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> Dict[str, Any]:
        query_value = data.get("query", {}).get("value", None)
        if query_value is None:
            return {}

        query_info = {}
        analyzer = InfrahubGraphQLQueryAnalyzer(query=query_value, schema=info.schema, branch=branch)

        valid, errors = analyzer.is_valid
        if not valid:
            raise ValueError(f"Query is not valid, {str(errors)}")

        query_info["models"] = {"value": sorted(list(await analyzer.get_models_in_use(types=info.context.types)))}
        query_info["depth"] = {"value": await analyzer.calculate_depth()}
        query_info["height"] = {"value": await analyzer.calculate_height()}
        query_info["operations"] = {
            "value": sorted([operation.operation_type.value for operation in analyzer.operations])
        }
        query_info["variables"] = {"value": [variable.dict() for variable in analyzer.variables]}

        return query_info

    @classmethod
    async def mutate_create(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context

        data.update(await cls.extract_query_info(info=info, data=data, branch=context.branch))

        obj, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        return obj, result

    @classmethod
    async def mutate_update(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context

        data.update(await cls.extract_query_info(info=info, data=data, branch=context.branch))

        obj, result = await super().mutate_update(root=root, info=info, data=data, branch=branch, at=at)

        return obj, result
