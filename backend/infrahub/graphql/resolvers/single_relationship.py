from typing import TYPE_CHECKING, Any

from graphql import GraphQLResolveInfo
from graphql.type.definition import GraphQLNonNull

from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.field_extractor import extract_graphql_fields

from ..loaders.node import GetManyParams, NodeDataLoader
from ..types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED

if TYPE_CHECKING:
    from infrahub.core.schema.node_schema import NodeSchema

    from ..initialization import GraphqlContext


class SingleRelationshipResolver:
    def __init__(self) -> None:
        self._data_loader_instances: dict[GetManyParams, NodeDataLoader] = {}

    def _get_metadata_to_include(self, property_fields: dict[str, Any]) -> MetadataOptions:
        include_metadata = MetadataOptions.NONE
        if "created_at" in property_fields:
            include_metadata |= MetadataOptions.CREATED_AT
        if "created_by" in property_fields:
            include_metadata |= MetadataOptions.CREATED_BY
        if "updated_at" in property_fields:
            include_metadata |= MetadataOptions.UPDATED_AT
        if "updated_by" in property_fields:
            include_metadata |= MetadataOptions.UPDATED_BY
        if "source" in property_fields:
            include_metadata |= MetadataOptions.SOURCE
        if "owner" in property_fields:
            include_metadata |= MetadataOptions.OWNER
        if "is_protected" in property_fields:
            include_metadata |= MetadataOptions.IS_PROTECTED
        return include_metadata

    def _build_relationship_meta_response(
        self, relationship: Relationship, metadata_fields: dict[str, Any]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for meta_field in metadata_fields.keys():
            if meta_field == "created_at":
                created_at = relationship._get_created_at()
                data["created_at"] = created_at.to_datetime() if created_at else None
            elif meta_field == "created_by":
                data["created_by"] = relationship._get_created_by()
            elif meta_field == "updated_at":
                updated_at = relationship._get_updated_at()
                data["updated_at"] = updated_at.to_datetime() if updated_at else None
            elif meta_field == "updated_by":
                data["updated_by"] = relationship._get_updated_by()
        return data

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
        fields = extract_graphql_fields(info=info)
        node_fields = fields.get("node", {})
        property_fields = fields.get("properties", {})
        metadata_fields = {
            "node_metadata": fields.get("node_metadata", {}),
            "relationship_metadata": fields.get("relationship_metadata", {}),
        }
        for key, value in property_fields.items():
            mapped_name = RELATIONS_PROPERTY_MAP[key]
            node_fields[mapped_name] = value

        metadata_field_names = {prop_name for prop_name in RELATIONS_PROPERTY_MAP if prop_name != "__typename"}
        requires_relationship_properties = bool(set(property_fields.keys()) & metadata_field_names)
        requires_relationship_metadata = bool(metadata_fields["relationship_metadata"])

        # Extract the schema of the node on the other end of the relationship from the GQL Schema
        node_rel = node_schema.get_relationship(info.field_name)

        response: dict[str, Any] = {"node": None, "properties": {}}

        relationship: Relationship | None = None
        peer_node: Node | None = None

        if requires_relationship_properties or requires_relationship_metadata:
            include_metadata = self._get_metadata_to_include(property_fields=property_fields)
            if requires_relationship_metadata:
                include_metadata |= self._get_metadata_to_include(
                    property_fields=metadata_fields["relationship_metadata"]
                )
            relationship = await self._get_entities_simple(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                field_name=info.field_name,
                parent_id=parent["id"],
                source_kind=node_schema.kind,
                rel_schema=node_rel,
                node_fields=node_fields,
                metadata_fields=metadata_fields,
                include_metadata=include_metadata,
                **kwargs,
            )
        else:
            peer_node = await self._get_entities_with_data_loader(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                rel_schema=node_rel,
                parent=parent,
                node_fields=node_fields,
                metadata_fields=metadata_fields,
            )

        if not relationship and not peer_node:
            return response

        async with graphql_context.db.start_session(read_only=True) as db:
            if relationship:
                node_graph = await relationship.to_graphql(
                    db=db, fields=node_fields, related_node_ids=graphql_context.related_node_ids
                )
                peer_node = await relationship.get_peer(db=db)
            elif peer_node:
                node_graph = await peer_node.to_graphql(
                    db=db, fields=node_fields, related_node_ids=graphql_context.related_node_ids
                )

            response["node"] = node_graph

            for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
                value = node_graph.pop(key, None)
                if value:
                    response["properties"][mapped] = value

            if metadata_fields.get("node_metadata") and peer_node:
                response["node_metadata"] = await peer_node._build_meta_response("node_metadata", fields)

            if metadata_fields.get("relationship_metadata") and relationship:
                response["relationship_metadata"] = self._build_relationship_meta_response(
                    relationship=relationship, metadata_fields=metadata_fields["relationship_metadata"]
                )

        return response

    async def _get_entities_simple(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        field_name: str,
        parent_id: str,
        source_kind: str,
        rel_schema: RelationshipSchema,
        node_fields: dict[str, Any],
        metadata_fields: dict[str, dict[str, Any]],
        include_metadata: MetadataOptions,
        **kwargs: Any,
    ) -> Relationship | None:
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
                metadata_fields=metadata_fields.get("node_metadata"),
                at=at,
                branch=branch,
                branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC,
                fetch_peers=True,
                include_metadata=include_metadata,
            )
            if not objs:
                return None
            return objs[0]

    async def _get_entities_with_data_loader(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        rel_schema: RelationshipSchema,
        parent: dict[str, Any],
        node_fields: dict[str, Any],
        metadata_fields: dict[str, dict[str, Any]],
    ) -> Node | None:
        try:
            peer_id: str = parent[rel_schema.name][0]["node"]["id"]
        except (KeyError, IndexError):
            return None

        if node_fields and "hfid" in node_fields:
            node_fields["human_friendly_id"] = None

        query_params = GetManyParams(
            fields=node_fields,
            metadata_fields=metadata_fields.get("node_metadata"),
            at=at,
            branch=branch,
            include_metadata=MetadataOptions.LINKED_NODES,
            prefetch_relationships=False,
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
        return node
