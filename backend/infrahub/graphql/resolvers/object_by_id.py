"""Resolver for a field that names one object by id, such as an attribute's `source` or `owner`."""

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


class ObjectByIdResolver:
    """Load the objects the fields of one request name by id, in batches, each object once.

    One loader serves every field read with the same branch, time and sub-selection, whichever field it
    is, so a page of objects costs one read for everything its fields name, and an object named by
    several fields is loaded once.
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
        )
        if query_params not in self._data_loader_instances:
            self._data_loader_instances[query_params] = NodeDataLoader(db=db, query_params=query_params)
        return self._data_loader_instances[query_params]

    async def resolve(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
        """Resolve a field whose parent dict holds `{"id": ...}` under the field's name, or None."""
        reference = parent.get(info.field_name)
        if not reference or not reference.get("id"):
            return None

        graphql_context: GraphqlContext = info.context
        fields = extract_graphql_fields(info=info)
        if "hfid" in fields:
            fields["human_friendly_id"] = None
        loader = self._get_or_create_loader(
            db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at, fields=fields
        )
        obj = await loader.load(reference["id"])
        if obj is None:
            return None
        return await obj.to_graphql(
            db=graphql_context.db, fields=fields, related_node_ids=graphql_context.related_node_ids
        )


@retry_db_transaction(name="object_by_id_resolver")
async def object_by_id_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
    """Function resolver that delegates to the ObjectByIdResolver on the context."""
    graphql_context: GraphqlContext = info.context
    return await graphql_context.object_by_id_resolver.resolve(parent=parent, info=info)
