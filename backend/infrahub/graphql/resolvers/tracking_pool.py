"""Resolver for the pool a number attribute's `from_pool` output field references."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.database import retry_db_transaction
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.loaders.node import GetManyParams, NodeDataLoader
from infrahub.graphql.metadata import build_metadata_query_options

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch.models import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


class TrackingPoolResolver:
    """Load the number pools referenced by `from_pool.pool` across one request in batches.

    One loader serves every attribute whose pool is read with the same branch, time and fields, so
    a page of nodes costs one pool read. When the pool node is not found, the field resolves to
    null and GraphQL nulls the enclosing `from_pool` object because `pool` is non-nullable.
    """

    def __init__(self) -> None:
        self._data_loader_instances: dict[GetManyParams, NodeDataLoader] = {}

    def _get_or_create_loader(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        fields: dict[str, Any],
    ) -> NodeDataLoader:
        query_params = GetManyParams(
            fields=fields,
            at=at,
            branch=branch,
            include_metadata=build_metadata_query_options(node_fields=fields),
            branch_agnostic=True,
        )
        if query_params not in self._data_loader_instances:
            self._data_loader_instances[query_params] = NodeDataLoader(db=db, query_params=query_params)
        return self._data_loader_instances[query_params]

    async def resolve(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
        """Resolve `pool` on a `from_pool` object, whose parent dict holds `{"pool": {"id": ...}}`."""
        pool_reference = parent.get("pool")
        if not pool_reference or not pool_reference.get("id"):
            return None

        graphql_context: GraphqlContext = info.context
        fields = extract_graphql_fields(info=info)
        loader = self._get_or_create_loader(
            db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at, fields=fields
        )
        node = await loader.load(pool_reference["id"])
        if node is None:
            return None
        return await node.to_graphql(
            db=graphql_context.db, fields=fields, related_node_ids=graphql_context.related_node_ids
        )


@retry_db_transaction(name="tracking_pool_resolver")
async def tracking_pool_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
    """Function resolver that delegates to the TrackingPoolResolver on the context."""
    graphql_context: GraphqlContext = info.context
    return await graphql_context.tracking_pool_resolver.resolve(parent=parent, info=info)
