from typing import TYPE_CHECKING, Any

from graphql import GraphQLResolveInfo
from graphql.type.definition import GraphQLNonNull
from infrahub_sdk.utils import deep_merge_dict, extract_fields

from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.manager import NodeManager
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..loaders.node import GetManyParams, NodeDataLoader
from ..types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED

if TYPE_CHECKING:
    from infrahub.core.schema.node_schema import NodeSchema

    from ..initialization import GraphqlContext


class SingleRelationshipResolver:
    def __init__(self) -> None:
        self._data_loader_instances: dict[GetManyParams, NodeDataLoader] = {}

    async def resolve(self, parent: dict, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
        """Resolver for relationships of cardinality=one for Edged responses

        This resolver is used for paginated responses and as such we redefined the requested
        fields by only reusing information below the 'node' key.
        """
        # Extract the InfraHub schema by inspecting the GQL Schema

        # :
        node_schema: NodeSchema = (
            info.parent_type.of_type.graphene_type._meta.schema
            if isinstance(info.parent_type, GraphQLNonNull)
            else info.parent_type.graphene_type._meta.schema  # type: ignore[attr-defined]
        )

        graphql_context: GraphqlContext = info.context

        # Extract the name of the fields in the GQL query
        fields = await extract_fields(info.field_nodes[0].selection_set)
        node_fields = fields.get("node", {})
        property_fields = fields.get("properties", {})
        for key, value in property_fields.items():
            mapped_name = RELATIONS_PROPERTY_MAP[key]
            node_fields[mapped_name] = value

        metadata_field_names = {prop_name for prop_name in RELATIONS_PROPERTY_MAP if prop_name != "__typename"}
        requires_relationship_metadata = bool(set(property_fields.keys()) & metadata_field_names)

        # Extract the schema of the node on the other end of the relationship from the GQL Schema
        node_rel = node_schema.get_relationship(info.field_name)

        response: dict[str, Any] = {"node": None, "properties": {}}

        if requires_relationship_metadata:
            node_graph = await self._get_entities_simple(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                related_node_ids=graphql_context.related_node_ids,
                field_name=info.field_name,
                parent_id=parent["id"],
                source_kind=node_schema.kind,
                rel_schema=node_rel,
                node_fields=node_fields,
                **kwargs,
            )
        else:
            node_graph = await self._get_entities_with_data_loader(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                related_node_ids=graphql_context.related_node_ids,
                rel_schema=node_rel,
                parent=parent,
                node_fields=node_fields,
            )

        if not node_graph:
            return response
        response["node"] = node_graph

        for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
            value = node_graph.pop(key, None)
            if value:
                response["properties"][mapped] = value
        return response

    async def _get_entities_simple(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        related_node_ids: set[str] | None,
        field_name: str,
        parent_id: str,
        source_kind: str,
        rel_schema: RelationshipSchema,
        node_fields: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        filters = {
            f"{field_name}__{key}": value
            for key, value in kwargs.items()
            if ("__" in key and value) or key in ["id", "ids"]
        }
        async with db.start_session(read_only=True) as dbs:
            objs = await NodeManager.query_peers(
                db=dbs,
                ids=[parent_id],
                source_kind=source_kind,
                schema=rel_schema,
                filters=filters,
                fields=node_fields,
                at=at,
                branch=branch,
                branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
                fetch_peers=True,
            )
            if not objs:
                return None
            return await objs[0].to_graphql(db=dbs, fields=node_fields, related_node_ids=related_node_ids)

    async def _get_entities_with_data_loader(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        related_node_ids: set[str] | None,
        rel_schema: RelationshipSchema,
        parent: dict[str, Any],
        node_fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            peer_id: str = parent[rel_schema.name][0]["node"]["id"]
        except (KeyError, IndexError):
            return None

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

        query_params = GetManyParams(
            fields=node_fields,
            at=at,
            branch=branch,
            include_source=True,
            include_owner=True,
            prefetch_relationships=False,
            account=None,
            branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
        )
        if query_params in self._data_loader_instances:
            loader = self._data_loader_instances[query_params]
        else:
            loader = NodeDataLoader(db=db, query_params=query_params)
            self._data_loader_instances[query_params] = loader
        node = await loader.load(key=peer_id)
        if not node:
            return None
        async with db.start_session(read_only=True) as dbs:
            return await node.to_graphql(db=dbs, fields=node_fields, related_node_ids=related_node_ids)
