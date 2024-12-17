from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from aiodataloader import DataLoader
from infrahub_sdk.utils import deep_merge_dict, extract_fields

from infrahub.auth import AccountSession
from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind, RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFoundError

from .parser import extract_selection
from .permissions import get_permissions
from .types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.schema import MainSchemaTypes, NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


async def account_resolver(
    root,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
) -> dict:
    fields = await extract_fields(info.field_nodes[0].selection_set)
    context: GraphqlContext = info.context

    async with context.db.start_session() as db:
        results = await NodeManager.query(
            schema=InfrahubKind.GENERICACCOUNT,
            filters={"ids": [context.account_session.account_id]},
            fields=fields,
            db=db,
        )
        if results:
            account_profile = await results[0].to_graphql(db=db, fields=fields)
            return account_profile

        raise NodeNotFoundError(node_type=InfrahubKind.GENERICACCOUNT, identifier=context.account_session.account_id)


async def default_resolver(*args: Any, **kwargs) -> dict | list[dict] | None:
    """Not sure why but the default resolver returns sometime 4 positional args and sometime 2.

    When it returns 4, they are organized as follow
        - field name
        - ???
        - parent
        - info
    When it returns 2, they are organized as follow
        - parent
        - info
    """

    parent = None
    info = None
    field_name = None

    if len(args) == 4:
        parent = args[2]
        info = args[3]
        field_name = args[0]
    elif len(args) == 2:
        parent = args[0]
        info = args[1]
        field_name = info.field_name
    else:
        raise ValueError(f"expected either 2 or 4 args for default_resolver, got {len(args)}")

    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # If the field is an attribute, return its value directly
    if field_name not in node_schema.relationship_names:
        return parent.get(field_name, None)

    # Extract the contextual information from the request context
    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    async with context.db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            ids=[parent["id"]],
            source_kind=node_schema.kind,
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=context.at,
            branch=context.branch,
            branch_agnostic=node_rel.branch is BranchSupportType.AGNOSTIC,
            fetch_peers=True,
        )

        if node_rel.cardinality == "many":
            return [
                await obj.to_graphql(db=db, fields=fields, related_node_ids=context.related_node_ids) for obj in objs
            ]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(db=db, fields=fields, related_node_ids=context.related_node_ids)


async def parent_field_name_resolver(parent: dict[str, dict], info: GraphQLResolveInfo) -> dict:
    """This resolver gets used when we know that the parent resolver has already gathered the required information.

    An example of this is the permissions field at the top level within default_paginated_list_resolver()
    """

    return parent[info.field_name]


async def default_paginated_list_resolver(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
    offset: int | None = None,
    limit: int | None = None,
    partial_match: bool = False,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    schema: MainSchemaTypes = info.return_type.graphene_type._meta.schema
    fields = await extract_selection(info.field_nodes[0], schema=schema)

    context: GraphqlContext = info.context
    async with context.db.start_session() as db:
        response: dict[str, Any] = {"edges": []}
        filters = {
            key: value for key, value in kwargs.items() if ("__" in key and value is not None) or key in ("ids", "hfid")
        }

        edges = fields.get("edges", {})
        node_fields = edges.get("node", {})

        permission_set: Optional[dict[str, Any]] = None
        permissions = await get_permissions(db=db, schema=schema, context=context) if context.account_session else None
        if fields.get("permissions"):
            response["permissions"] = permissions

        if permissions:
            for edge in permissions["edges"]:
                if edge["node"]["kind"] == schema.kind:
                    permission_set = edge["node"]

        objs = []
        if edges or "hfid" in filters:
            objs = await NodeManager.query(
                db=db,
                schema=schema,
                filters=filters or None,
                fields=node_fields,
                at=context.at,
                branch=context.branch,
                limit=limit,
                offset=offset,
                account=context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=partial_match,
            )

        if "count" in fields:
            if filters.get("hfid"):
                response["count"] = len(objs)
            else:
                response["count"] = await NodeManager.count(
                    db=db,
                    schema=schema,
                    filters=filters,
                    at=context.at,
                    branch=context.branch,
                    partial_match=partial_match,
                )

        # get peer IDs for relationships
        if objs:
            objects = [
                {
                    "node": await obj.to_graphql(
                        db=db,
                        fields=node_fields,
                        related_node_ids=context.related_node_ids,
                        permissions=permission_set,
                    )
                }
                for obj in objs
            ]
            response["edges"] = objects

        return response


@dataclass
class GetEntitiesParams:
    fields: dict | None = None
    at: Timestamp | str | None = None
    branch: Branch | str | None = None
    include_source: bool = False
    include_owner: bool = False
    prefetch_relationships: bool = False
    account: AccountSession | None = None
    branch_agnostic: bool = False

    def __hash__(self) -> int:
        frozen_fields: frozenset | None = None
        if self.fields:
            frozen_fields = to_frozen_set(self.fields)
        timestamp = Timestamp(self.at)
        branch = self.branch.name if isinstance(self.branch, Branch) else self.branch
        account_id = self.account.id if isinstance(self.account, AccountSession) else None
        hash_str = "|".join(
            [
                str(hash(frozen_fields)),
                timestamp.to_string(),
                branch,
                str(self.include_source),
                str(self.include_owner),
                str(self.prefetch_relationships),
                str(account_id),
                str(self.branch_agnostic),
            ]
        )
        return hash(hash_str)


def to_frozen_set(to_freeze: dict[str, Any]) -> frozenset:
    freezing_dict = {}
    for k, v in to_freeze.items():
        if isinstance(v, dict):
            freezing_dict[k] = to_frozen_set(v)
        elif isinstance(v, (list, set)):
            freezing_dict[k] = frozenset(v)
        else:
            freezing_dict[k] = v
    return frozenset(freezing_dict)


class EntityDataLoader(DataLoader[str, Node]):
    def __init__(self, db: InfrahubDatabase, query_params: GetEntitiesParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.query_params = query_params
        self.db = db

    async def batch_load_fn(self, keys: list[Any]) -> list[Node]:  # pylint: disable=method-hidden
        async with self.db.start_session() as db:
            nodes_by_id = await NodeManager.get_many(
                db=db,
                ids=keys,
                fields=self.query_params.fields,
                at=self.query_params.at,
                branch=self.query_params.branch,
                include_source=self.query_params.include_source,
                include_owner=self.query_params.include_owner,
                prefetch_relationships=self.query_params.prefetch_relationships,
                account=self.query_params.account,
                branch_agnostic=self.query_params.branch_agnostic,
            )
        results = []
        for node_id in keys:
            results.append(nodes_by_id.get(node_id, None))
        return results


async def single_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:
    context: GraphqlContext = info.context
    resolver = context.single_relationship_resolver
    return await resolver.resolve(parent=parent, info=info, **kwargs)


class SingleRelationshipResolver:
    def __init__(self) -> None:
        self._data_loader_instances: dict[GetEntitiesParams, EntityDataLoader] = {}

    async def resolve(self, parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:  # pylint: disable=unused-argument
        """Resolver for relationships of cardinality=one for Edged responses

        This resolver is used for paginated responses and as such we redefined the requested
        fields by only reusing information below the 'node' key.
        """
        # Extract the InfraHub schema by inspecting the GQL Schema

        node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

        context: GraphqlContext = info.context

        # Extract the name of the fields in the GQL query
        fields = await extract_fields(info.field_nodes[0].selection_set)
        node_fields = fields.get("node", {})
        property_fields = fields.get("properties", {})
        for key, value in property_fields.items():
            mapped_name = RELATIONS_PROPERTY_MAP[key]
            node_fields[mapped_name] = value

        # Extract the schema of the node on the other end of the relationship from the GQL Schema
        node_rel = node_schema.get_relationship(info.field_name)

        response: dict[str, Any] = {"node": None, "properties": {}}
        try:
            peer_id: str = parent[node_rel.name][0]["node"]["id"]
        except (KeyError, IndexError):
            return response

        if node_fields and "display_label" in node_fields:
            schema_branch = context.db.schema.get_schema_branch(name=context.branch.name)
            display_label_fields = schema_branch.generate_fields_for_display_label(name=node_rel.peer)
            if display_label_fields:
                node_fields = deep_merge_dict(dicta=node_fields, dictb=display_label_fields)

        if node_fields and "hfid" in node_fields:
            peer_schema = context.db.schema.get(name=node_rel.peer, branch=context.branch, duplicate=False)
            hfid_fields = peer_schema.generate_fields_for_hfid()
            if hfid_fields:
                node_fields = deep_merge_dict(dicta=node_fields, dictb=hfid_fields)

        query_params = GetEntitiesParams(
            fields=node_fields,
            at=context.at,
            branch=context.branch,
            include_source=True,
            include_owner=True,
            prefetch_relationships=False,
            account=None,
            branch_agnostic=node_rel.branch is BranchSupportType.AGNOSTIC,
        )
        if query_params in self._data_loader_instances:
            loader = self._data_loader_instances[query_params]
        else:
            loader = EntityDataLoader(db=context.db, query_params=query_params)
            self._data_loader_instances[query_params] = loader
        result = await loader.load(key=peer_id)

        if not result:
            return response

        node_graph = await result.to_graphql(
            db=context.db, fields=node_fields, related_node_ids=context.related_node_ids
        )

        for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
            value = node_graph.pop(key, None)
            if value:
                response["properties"][mapped] = value
        response["node"] = node_graph
        return response


async def many_relationship_resolver(
    parent: dict, info: GraphQLResolveInfo, include_descendants: Optional[bool] = False, **kwargs
) -> dict[str, Any]:
    """Resolver for relationships of cardinality=many for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})
    property_fields = edges.get("properties", {})
    for key, value in property_fields.items():
        mapped_name = RELATIONS_PROPERTY_MAP[key]
        node_fields[mapped_name] = value

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    offset = kwargs.pop("offset", None)
    limit = kwargs.pop("limit", None)

    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    response: dict[str, Any] = {"edges": [], "count": None}

    source_kind = node_schema.kind

    async with context.db.start_session() as db:
        ids = [parent["id"]]
        if include_descendants:
            query = await NodeGetHierarchyQuery.init(
                db=db,
                direction=RelationshipHierarchyDirection.DESCENDANTS,
                node_id=parent["id"],
                node_schema=node_schema,
                at=context.at,
                branch=context.branch,
            )
            if node_schema.hierarchy:
                source_kind = node_schema.hierarchy
            await query.execute(db=db)
            descendants_ids = list(query.get_peer_ids())
            ids.extend(descendants_ids)

        if "count" in fields:
            response["count"] = await NodeManager.count_peers(
                db=db,
                ids=ids,
                source_kind=source_kind,
                schema=node_rel,
                filters=filters,
                at=context.at,
                branch=context.branch,
                branch_agnostic=node_rel.branch is BranchSupportType.AGNOSTIC,
            )

        if not node_fields:
            return response

        objs = await NodeManager.query_peers(
            db=db,
            ids=ids,
            source_kind=source_kind,
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            offset=offset,
            limit=limit,
            at=context.at,
            branch=context.branch,
            branch_agnostic=node_rel.branch is BranchSupportType.AGNOSTIC,
            fetch_peers=True,
        )

        if not objs:
            return response
        node_graph = [
            await obj.to_graphql(db=db, fields=node_fields, related_node_ids=context.related_node_ids) for obj in objs
        ]

        entries = []
        for node in node_graph:
            entry = {"node": {}, "properties": {}}
            for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
                value = node.pop(key, None)
                if value:
                    entry["properties"][mapped] = value
            entry["node"] = node
            entries.append(entry)
        response["edges"] = entries

        return response


async def ancestors_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.ANCESTORS, parent=parent, info=info, **kwargs
    )


async def descendants_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.DESCENDANTS, parent=parent, info=info, **kwargs
    )


async def hierarchy_resolver(
    direction: RelationshipHierarchyDirection, parent: dict, info: GraphQLResolveInfo, **kwargs
) -> dict[str, Any]:
    """Resolver for ancestors and dependants for Hierarchical nodes

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    offset = kwargs.pop("offset", None)
    limit = kwargs.pop("limit", None)

    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    response: dict[str, Any] = {"edges": [], "count": None}

    async with context.db.start_session() as db:
        if "count" in fields:
            response["count"] = await NodeManager.count_hierarchy(
                db=db,
                id=parent["id"],
                direction=direction,
                node_schema=node_schema,
                filters=filters,
                at=context.at,
                branch=context.branch,
            )

        if not node_fields:
            return response

        objs = await NodeManager.query_hierarchy(
            db=db,
            id=parent["id"],
            direction=direction,
            node_schema=node_schema,
            filters=filters,
            fields=node_fields,
            offset=offset,
            limit=limit,
            at=context.at,
            branch=context.branch,
        )

        if not objs:
            return response
        node_graph = [await obj.to_graphql(db=db, fields=node_fields) for obj in objs.values()]

        entries = []
        for node in node_graph:
            entry = {"node": {}, "properties": {}}
            entry["node"] = node
            entries.append(entry)
        response["edges"] = entries

        return response
