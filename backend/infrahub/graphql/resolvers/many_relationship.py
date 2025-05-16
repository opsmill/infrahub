from typing import TYPE_CHECKING, Any

from graphql import GraphQLResolveInfo
from infrahub_sdk.utils import deep_merge_dict, extract_fields

from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType, RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..loaders.peers import PeerRelationshipsDataLoader, QueryPeerParams
from ..types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

    from ..initialization import GraphqlContext


class ManyRelationshipResolver:
    def __init__(self) -> None:
        self._data_loader_instances: dict[QueryPeerParams, PeerRelationshipsDataLoader] = {}

    async def get_descendant_ids(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        parent_id: str,
        node_schema: NodeSchema,
    ) -> list[str]:
        async with db.start_session(read_only=True) as dbs:
            query = await NodeGetHierarchyQuery.init(
                db=dbs,
                direction=RelationshipHierarchyDirection.DESCENDANTS,
                node_id=parent_id,
                node_schema=node_schema,
                at=at,
                branch=branch,
            )
            await query.execute(db=dbs)
        return list(query.get_peer_ids())

    async def get_peer_count(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        ids: list[str],
        source_kind: str,
        rel_schema: RelationshipSchema,
        filters: dict[str, Any],
    ) -> int:
        async with db.start_session(read_only=True) as dbs:
            return await NodeManager.count_peers(
                db=dbs,
                ids=ids,
                source_kind=source_kind,
                schema=rel_schema,
                filters=filters,
                at=at,
                branch=branch,
                branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
            )

    async def resolve(
        self,
        parent: dict,
        info: GraphQLResolveInfo,
        include_descendants: bool = False,
        offset: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Resolver for relationships of cardinality=one for Edged responses

        This resolver is used for paginated responses and as such we redefined the requested
        fields by only reusing information below the 'node' key.
        """
        # Extract the InfraHub schema by inspecting the GQL Schema

        node_schema: MainSchemaTypes = info.parent_type.graphene_type._meta.schema  # type: ignore[attr-defined]

        graphql_context: GraphqlContext = info.context

        # Extract the name of the fields in the GQL query
        fields = await extract_fields(info.field_nodes[0].selection_set)
        edges = fields.get("edges", {})
        node_fields = edges.get("node", {})
        property_fields = edges.get("properties", {})
        for key, value in property_fields.items():
            mapped_name = RELATIONS_PROPERTY_MAP[key]
            node_fields[mapped_name] = value

        filters = {
            f"{info.field_name}__{key}": value
            for key, value in kwargs.items()
            if "__" in key and value or key in ["id", "ids"]
        }

        response: dict[str, Any] = {"edges": [], "count": None}

        # Extract the schema of the node on the other end of the relationship from the GQL Schema
        node_rel = node_schema.get_relationship(info.field_name)
        source_kind = node_schema.kind
        ids = [parent["id"]]
        if isinstance(node_schema, NodeSchema):
            if node_schema.hierarchy:
                source_kind = node_schema.hierarchy

            if include_descendants:
                descendant_ids = await self.get_descendant_ids(
                    db=graphql_context.db,
                    branch=graphql_context.branch,
                    at=graphql_context.at,
                    parent_id=ids[0],
                    node_schema=node_schema,
                )
                ids.extend(descendant_ids)

        if "count" in fields:
            peer_count = await self.get_peer_count(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                ids=ids,
                source_kind=source_kind,
                rel_schema=node_rel,
                filters=filters,
            )
            response["count"] = peer_count

        if not node_fields:
            return response

        if offset or limit:
            node_graph = await self._get_entities_simple(
                db=graphql_context.db,
                branch=graphql_context.branch,
                ids=ids,
                at=graphql_context.at,
                related_node_ids=graphql_context.related_node_ids,
                source_kind=source_kind,
                rel_schema=node_rel,
                filters=filters,
                node_fields=node_fields,
                offset=offset,
                limit=limit,
            )
        else:
            node_graph = await self._get_entities_with_data_loader(
                db=graphql_context.db,
                branch=graphql_context.branch,
                ids=ids,
                at=graphql_context.at,
                related_node_ids=graphql_context.related_node_ids,
                source_kind=source_kind,
                rel_schema=node_rel,
                filters=filters,
                node_fields=node_fields,
            )

        if not node_graph:
            return response

        entries = []
        for node in node_graph:
            entry: dict[str, dict[str, Any]] = {"node": {}, "properties": {}}
            for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
                value = node.pop(key, None)
                if value:
                    entry["properties"][mapped] = value
            entry["node"] = node
            entries.append(entry)

        response["edges"] = entries
        return response

    async def _get_entities_simple(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        ids: list[str],
        at: Timestamp | None,
        related_node_ids: set[str] | None,
        source_kind: str,
        rel_schema: RelationshipSchema,
        filters: dict[str, Any],
        node_fields: dict[str, Any],
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]] | None:
        async with db.start_session(read_only=True) as dbs:
            objs = await NodeManager.query_peers(
                db=dbs,
                ids=ids,
                source_kind=source_kind,
                schema=rel_schema,
                filters=filters,
                fields=node_fields,
                offset=offset,
                limit=limit,
                at=at,
                branch=branch,
                branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
                fetch_peers=True,
            )
            if not objs:
                return None
            return [await obj.to_graphql(db=dbs, fields=node_fields, related_node_ids=related_node_ids) for obj in objs]

    async def _get_entities_with_data_loader(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        ids: list[str],
        at: Timestamp | None,
        related_node_ids: set[str] | None,
        source_kind: str,
        rel_schema: RelationshipSchema,
        filters: dict[str, Any],
        node_fields: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        if node_fields and "display_label" in node_fields:
            schema_branch = db.schema.get_schema_branch(name=branch.name)
            display_label_fields = schema_branch.generate_fields_for_display_label(name=rel_schema.peer)
            if display_label_fields:
                node_fields = deep_merge_dict(dicta=node_fields, dictb=display_label_fields)

        if node_fields and "hfid" in node_fields:
            peer_schema = db.schema.get(name=rel_schema.peer, branch=branch, duplicate=False)
            hfid_fields = peer_schema.generate_fields_for_hfid()
            if hfid_fields:
                node_fields = deep_merge_dict(dicta=node_fields, dictb=hfid_fields)

        query_params = QueryPeerParams(
            branch=branch,
            source_kind=source_kind,
            schema=rel_schema,
            filters=filters,
            fields=node_fields,
            at=at,
            branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
        )
        if query_params in self._data_loader_instances:
            loader = self._data_loader_instances[query_params]
        else:
            loader = PeerRelationshipsDataLoader(db=db, query_params=query_params)
            self._data_loader_instances[query_params] = loader
        all_peer_rels = []
        for node_id in ids:
            node_peer_rels = await loader.load(key=node_id)
            all_peer_rels.extend(node_peer_rels)
        if not all_peer_rels:
            return None
        async with db.start_session(read_only=True) as dbs:
            return [
                await obj.to_graphql(db=dbs, fields=node_fields, related_node_ids=related_node_ids)
                for obj in all_peer_rels
            ]
