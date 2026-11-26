"""Resolvers for the owner fields of node metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiodataloader import DataLoader

from infrahub.core.manager import NodeManager
from infrahub.core.ownership.models import (
    HolderKey,
    OwnerReference,
    ResolvedOwnership,
    StoredNodeOwnership,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolution import resolve_target_ownership
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.database import retry_db_transaction

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
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


class FieldOwnershipLoader(DataLoader[tuple[str, HolderKey], ResolvedOwnership | None]):
    """Load the owners that apply to the fields that one request asks for, with one batch for all nodes and fields.

    A key is the ID of a node with the holder of the owners of one of its fields.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = db
        self.branch = branch
        self.at = at

    async def batch_load_fn(self, keys: list[tuple[str, HolderKey]]) -> list[ResolvedOwnership | None]:
        async with self.db.start_session(read_only=True) as db:
            repository = OwnershipRepository(db=db, branch=self.branch, at=self.at)
            resolved = await OwnershipResolver(repository=repository).resolve_fields(fields=keys)
        return [resolved.get(key) for key in keys]


class StoredOwnershipLoader(DataLoader[str, StoredNodeOwnership | None]):
    """Load the owner states that the nodes of one request store, with one batch."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = db
        self.branch = branch
        self.at = at

    async def batch_load_fn(self, keys: list[str]) -> list[StoredNodeOwnership | None]:
        async with self.db.start_session(read_only=True) as db:
            stored = await OwnershipRepository(db=db, branch=self.branch, at=self.at).read(node_ids=keys)
        return [stored.get(key) for key in keys]


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


def field_ownership_reference(schema: MainSchemaTypes, node_id: str, field_name: str) -> dict[str, Any] | None:
    """Return the reference that the `ownership` of one field of a node resolves from, and None for another field."""
    holder = field_holder(schema=schema, field_name=field_name)
    return {"node_id": node_id, "holder": holder} if holder else None


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
        self._field_loaders: dict[tuple[str, str], FieldOwnershipLoader] = {}
        self._stored_loaders: dict[tuple[str, str], StoredOwnershipLoader] = {}
        self._metadata_node_loaders: dict[tuple[str, str], MetadataNodeLoader] = {}

    @staticmethod
    def _loader_key(context: GraphqlContext) -> tuple[str, str]:
        return context.branch.name, context.at.to_string() if context.at else ""

    def _node_loader(self, context: GraphqlContext) -> NodeOwnershipLoader:
        key = self._loader_key(context=context)
        if key not in self._node_loaders:
            self._node_loaders[key] = NodeOwnershipLoader(db=context.db, branch=context.branch, at=context.at)
        return self._node_loaders[key]

    def _field_loader(self, context: GraphqlContext) -> FieldOwnershipLoader:
        key = self._loader_key(context=context)
        if key not in self._field_loaders:
            self._field_loaders[key] = FieldOwnershipLoader(db=context.db, branch=context.branch, at=context.at)
        return self._field_loaders[key]

    def _stored_loader(self, context: GraphqlContext) -> StoredOwnershipLoader:
        key = self._loader_key(context=context)
        if key not in self._stored_loaders:
            self._stored_loaders[key] = StoredOwnershipLoader(db=context.db, branch=context.branch, at=context.at)
        return self._stored_loaders[key]

    def _metadata_node_loader(self, context: GraphqlContext) -> MetadataNodeLoader:
        key = self._loader_key(context=context)
        if key not in self._metadata_node_loaders:
            self._metadata_node_loaders[key] = MetadataNodeLoader(db=context.db, branch=context.branch, at=context.at)
        return self._metadata_node_loaders[key]

    async def resolve_ownership(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
        """Resolve the owners of a node or of one of its fields from the reference that the parent holds.

        The reference is `{"node_id": ...}` for a node, with `"holder"` for one field of the node.
        """
        reference = parent.get(info.field_name)
        if not reference:
            return None
        resolved: ResolvedOwnership | None
        if "holder" in reference:
            resolved = await self._field_loader(context=info.context).load((reference["node_id"], reference["holder"]))
        else:
            resolved = await self._node_loader(context=info.context).load(reference["node_id"])
        return _to_graphql(resolved=resolved) if resolved else None

    async def resolve_target_ownership(self, parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
        """Resolve the owners that a profile or an object template gives to its nodes, from its reference."""
        reference = parent.get(info.field_name)
        if not reference:
            return None
        stored = await self._stored_loader(context=info.context).load(reference["node_id"])
        return _to_graphql(resolved=resolve_target_ownership(node=stored)) if stored else None

    async def resolve_target_field_ownership(
        self, parent: dict[str, Any], info: GraphQLResolveInfo, fields: list[str] | None
    ) -> list[dict[str, Any]] | None:
        """Resolve the owners that a profile or an object template gives to the fields of its nodes.

        Args:
            parent: The node metadata, with the `{"node_id": ..., "target_kind": ...}` reference under the field name.
            info: The GraphQL execution info.
            fields: The names of the fields to return. None gives all attributes and relationships of the nodes.

        """
        reference = parent.get(info.field_name)
        if not reference:
            return None
        context: GraphqlContext = info.context
        stored = await self._stored_loader(context=context).load(reference["node_id"])
        if stored is None:
            return None
        schema = context.db.schema.get_schema_branch(name=context.branch.name).get(
            name=reference["target_kind"], duplicate=False
        )
        names = fields if fields is not None else [*schema.attribute_names, *schema.relationship_names]
        return [
            {"field": name, "ownership": _to_graphql(resolved=resolve_target_ownership(node=stored, holder=holder))}
            for name in names
            if (holder := field_holder(schema=schema, field_name=name)) is not None
        ]

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


@retry_db_transaction(name="target_ownership_resolver")
async def target_ownership_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> dict[str, Any] | None:
    graphql_context: GraphqlContext = info.context
    return await graphql_context.ownership_resolver.resolve_target_ownership(parent=parent, info=info)


@retry_db_transaction(name="target_field_ownership_resolver")
async def target_field_ownership_resolver(
    parent: dict[str, Any], info: GraphQLResolveInfo, fields: list[str] | None = None
) -> list[dict[str, Any]] | None:
    graphql_context: GraphqlContext = info.context
    return await graphql_context.ownership_resolver.resolve_target_field_ownership(
        parent=parent, info=info, fields=fields
    )


@retry_db_transaction(name="metadata_node_resolver")
async def metadata_node_resolver(parent: dict[str, Any], info: GraphQLResolveInfo) -> Any:
    graphql_context: GraphqlContext = info.context
    return await graphql_context.ownership_resolver.resolve_metadata_node_field(parent=parent, info=info)
