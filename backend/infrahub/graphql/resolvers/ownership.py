"""Resolvers for the owner fields of node metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiodataloader import DataLoader

from infrahub.core.manager import NodeManager
from infrahub.core.ownership.models import OwnerReference, ResolvedOwnership
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.database import retry_db_transaction

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


class NodeOwnershipLoader(DataLoader[str, ResolvedOwnership | None]):
    """Load the owners that apply to the nodes that the fields of one request ask for, with one batch."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = db
        self.branch = branch
        self.at = at

    async def batch_load_fn(self, keys: list[str]) -> list[ResolvedOwnership | None]:
        async with self.db.start_session(read_only=True) as db:
            repository = OwnershipRepository(db=db, branch=self.branch, at=self.at)
            resolved = await OwnershipResolver(repository=repository).resolve(node_ids=keys)
        return [resolved.get(key) for key in keys]


class MetadataNodeLoader(DataLoader[str, OwnerReference]):
    """Load the kind and the labels of the nodes that metadata refers to, whatever the permissions of the user."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = db
        self.branch = branch
        self.at = at

    async def batch_load_fn(self, keys: list[str]) -> list[OwnerReference]:
        references: list[OwnerReference] = []
        async with self.db.start_session(read_only=True) as db:
            nodes = await NodeManager.get_many(db=db, ids=list(keys), branch=self.branch, at=self.at)
            for key in keys:
                node = nodes.get(key)
                if node is None:
                    references.append(OwnerReference(id=key, kind=None, display_label=None, hfid=None, is_deleted=True))
                    continue
                hfid = await node.get_hfid(db=db)
                references.append(
                    OwnerReference(
                        id=key,
                        kind=node.get_kind(),
                        display_label=await node.get_display_label(db=db),
                        hfid=tuple(hfid) if hfid is not None else None,
                        is_deleted=False,
                    )
                )
        return references


def _to_graphql(resolved: ResolvedOwnership) -> dict[str, Any]:
    return {
        "state": resolved.state,
        "origin": resolved.origin,
        "origin_node": {"id": resolved.origin_node_id} if resolved.origin_node_id else None,
        "owners": [{"id": owner_id} for owner_id in resolved.owner_ids],
    }


class OwnershipGraphqlResolver:
    """Resolve the owner fields of one request with one batch for the owners and one for the nodes they refer to."""

    def __init__(self) -> None:
        self._node_loaders: dict[tuple[str, str], NodeOwnershipLoader] = {}
        self._metadata_node_loaders: dict[tuple[str, str], MetadataNodeLoader] = {}

    @staticmethod
    def _loader_key(context: GraphqlContext) -> tuple[str, str]:
        return context.branch.name, context.at.to_string() if context.at else ""

    def _node_loader(self, context: GraphqlContext) -> NodeOwnershipLoader:
        key = self._loader_key(context=context)
        if key not in self._node_loaders:
            self._node_loaders[key] = NodeOwnershipLoader(db=context.db, branch=context.branch, at=context.at)
        return self._node_loaders[key]

    def _metadata_node_loader(self, context: GraphqlContext) -> MetadataNodeLoader:
        key = self._loader_key(context=context)
        if key not in self._metadata_node_loaders:
            self._metadata_node_loaders[key] = MetadataNodeLoader(db=context.db, branch=context.branch, at=context.at)
        return self._metadata_node_loaders[key]

    async def resolve_ownership(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
        """Resolve the owners of a node from the `{"node_id": ...}` reference that the parent holds."""
        reference = parent.get(info.field_name)
        if not reference:
            return None
        resolved = await self._node_loader(context=info.context).load(reference["node_id"])
        return _to_graphql(resolved=resolved) if resolved else None

    async def load_metadata_nodes(self, context: GraphqlContext, node_ids: list[str]) -> list[OwnerReference]:
        """Return the kind and the labels that each node has now, or mark it as deleted."""
        return await self._metadata_node_loader(context=context).load_many(node_ids)

    async def resolve_metadata_node_field(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> Any:
        reference = await self._metadata_node_loader(context=info.context).load(parent["id"])
        return getattr(reference, info.field_name)


@retry_db_transaction(name="ownership_resolver")
async def ownership_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
    graphql_context: GraphqlContext = info.context
    return await graphql_context.ownership_resolver.resolve_ownership(parent=parent, info=info)


@retry_db_transaction(name="metadata_node_resolver")
async def metadata_node_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> Any:
    graphql_context: GraphqlContext = info.context
    return await graphql_context.ownership_resolver.resolve_metadata_node_field(parent=parent, info=info)
