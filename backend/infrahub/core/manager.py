from __future__ import annotations

from functools import reduce
from typing import TYPE_CHECKING, Any, Literal, Optional, TypeVar, Union, overload

from infrahub_sdk.utils import deep_merge_dict, is_valid_uuid

from infrahub.core.node import Node
from infrahub.core.node.delete_validator import NodeDeleteValidator
from infrahub.core.query.node import (
    AttributeFromDB,
    AttributeNodePropertyFromDB,
    NodeAttributesFromDB,
    NodeGetHierarchyQuery,
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
    NodeToProcess,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from infrahub.core.relationship import Relationship, RelationshipManager
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFoundError, ProcessingError, SchemaNotFoundError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.constants import RelationshipHierarchyDirection
    from infrahub.database import InfrahubDatabase

SchemaProtocol = TypeVar("SchemaProtocol")

# pylint: disable=redefined-builtin,too-many-lines


def identify_node_class(node: NodeToProcess) -> type[Node]:
    """Identify the proper class to use to create the NodeObject.

    If there is a class in the registry matching the name Kind, use it
    If there is a class in the registry matching one of the node Parent, use it
    Otherwise use Node
    """
    if node.schema.kind in registry.node:
        return registry.node[node.schema.kind]

    if node.schema.inherit_from:
        for parent in node.schema.inherit_from:
            if parent in registry.node:
                return registry.node[parent]

    return Node


def get_schema(
    db: InfrahubDatabase, branch: Branch, node_schema: type[SchemaProtocol] | MainSchemaTypes | str
) -> MainSchemaTypes:
    if isinstance(node_schema, str):
        return db.schema.get(name=node_schema, branch=branch.name)
    if hasattr(node_schema, "_is_runtime_protocol") and getattr(node_schema, "_is_runtime_protocol"):
        return db.schema.get(name=node_schema.__name__, branch=branch.name)
    if not isinstance(node_schema, (MainSchemaTypes)):
        raise ValueError(f"Invalid schema provided {node_schema}")

    return node_schema


class ProfileAttributeIndex:
    def __init__(
        self,
        profile_attributes_id_map: dict[str, NodeAttributesFromDB],
        profile_ids_by_node_id: dict[str, list[str]],
    ) -> None:
        self._profile_attributes_id_map = profile_attributes_id_map
        self._profile_ids_by_node_id = profile_ids_by_node_id

    def apply_profiles(self, node_data_dict: dict[str, Any]) -> dict[str, Any]:
        updated_data: dict[str, Any] = {**node_data_dict}
        node_id = node_data_dict.get("id")
        profile_ids = self._profile_ids_by_node_id.get(node_id, [])
        if not profile_ids:
            return updated_data
        profiles = [
            self._profile_attributes_id_map[p_id] for p_id in profile_ids if p_id in self._profile_attributes_id_map
        ]

        def get_profile_priority(nafd: NodeAttributesFromDB) -> tuple[Union[int, float], str]:
            try:
                return (int(nafd.attrs.get("profile_priority").value), nafd.node.get("uuid"))
            except (TypeError, AttributeError):
                return (float("inf"), "")

        profiles.sort(key=get_profile_priority)

        for attr_name, attr_data in updated_data.items():
            if not isinstance(attr_data, AttributeFromDB):
                continue
            if not attr_data.is_default:
                continue
            profile_value, profile_uuid = None, None
            index = 0

            while profile_value is None and index <= (len(profiles) - 1):
                try:
                    profile_value = profiles[index].attrs[attr_name].value
                    if profile_value != "NULL":
                        profile_uuid = profiles[index].node["uuid"]
                        break
                    profile_value = None
                except (IndexError, KeyError, AttributeError):
                    ...
                index += 1

            if profile_value is not None:
                attr_data.value = profile_value
                attr_data.is_from_profile = True
                attr_data.is_default = False
                attr_data.node_properties["source"] = AttributeNodePropertyFromDB(uuid=profile_uuid, labels=[])
        return updated_data


class NodeManager:
    @overload
    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        schema: Union[NodeSchema, GenericSchema, ProfileSchema, str],
        filters: dict | None = ...,
        fields: dict | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
        at: Union[Timestamp, str] | None = ...,
        branch: Union[Branch, str] | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        partial_match: bool = ...,
        branch_agnostic: bool = ...,
    ) -> list[Any]: ...

    @overload
    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        schema: type[SchemaProtocol],
        filters: dict | None = ...,
        fields: dict | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
        at: Union[Timestamp, str] | None = ...,
        branch: Union[Branch, str] | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        partial_match: bool = ...,
        branch_agnostic: bool = ...,
    ) -> list[SchemaProtocol]: ...

    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        schema: type[SchemaProtocol] | MainSchemaTypes | str,
        filters: dict | None = None,
        fields: dict | None = None,
        offset: int | None = None,
        limit: int | None = None,
        at: Union[Timestamp, str] | None = None,
        branch: Union[Branch, str] | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        partial_match: bool = False,
        branch_agnostic: bool = False,
    ) -> list[Any]:
        """Query one or multiple nodes of a given type based on filter arguments.

        Args:
            schema (NodeSchema or Str): Infrahub Schema or Name of a schema present in the registry.
            filters (dict, optional): filters provided in a dictionary
            fields (dict, optional): List of fields to include in the response.
            limit (int, optional): Maximum numbers of nodes to return. Defaults to 100.
            at (Timestamp or Str, optional): Timestamp for the query. Defaults to None.
            branch (Branch or Str, optional): Branch to query. Defaults to None.

        Returns:
            list[Node]: List of Node object
        """

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = get_schema(db=db, branch=branch, node_schema=schema)

        if filters and "hfid" in filters:
            node = await cls.get_one_by_hfid(
                db=db,
                hfid=filters["hfid"],
                kind=schema,
                fields=fields,
                at=at,
                branch=branch,
                include_source=include_source,
                include_owner=include_owner,
                prefetch_relationships=prefetch_relationships,
                account=account,
                branch_agnostic=branch_agnostic,
            )
            return [node] if node else []

        # Query the list of nodes matching this Query
        query = await NodeGetListQuery.init(
            db=db,
            schema=node_schema,
            branch=branch,
            offset=offset,
            limit=limit,
            filters=filters,
            at=at,
            partial_match=partial_match,
            branch_agnostic=branch_agnostic,
        )
        await query.execute(db=db)
        node_ids = query.get_node_ids()

        # if display_label or hfid has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            schema_branch = db.schema.get_schema_branch(name=branch.name)
            display_label_fields = schema_branch.generate_fields_for_display_label(name=node_schema.kind)
            if display_label_fields:
                fields = deep_merge_dict(dicta=fields, dictb=display_label_fields)

        if fields and "hfid" in fields and node_schema.human_friendly_id:
            hfid_fields = node_schema.generate_fields_for_hfid()
            if hfid_fields:
                fields = deep_merge_dict(dicta=fields, dictb=hfid_fields)

        response = await cls.get_many(
            ids=node_ids,
            fields=fields,
            branch=branch,
            account=account,
            at=at,
            include_source=include_source,
            include_owner=include_owner,
            db=db,
            prefetch_relationships=prefetch_relationships,
            branch_agnostic=branch_agnostic,
        )

        return list(response.values()) if node_ids else []

    @classmethod
    async def count(
        cls,
        db: InfrahubDatabase,
        schema: Union[type[SchemaProtocol], NodeSchema, GenericSchema, ProfileSchema, str],
        filters: Optional[dict] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        account=None,  # pylint: disable=unused-argument
        partial_match: bool = False,
        branch_agnostic: bool = False,
    ) -> int:
        """Return the total number of nodes using a given filter

        Args:
            schema (NodeSchema): Infrahub Schema or Name of a schema present in the registry.
            filters (dict, optional): filters provided in a dictionary
            at (Timestamp or Str, optional): Timestamp for the query. Defaults to None.
            branch (Branch or Str, optional): Branch to query. Defaults to None.

        Returns:
            int: The number of responses found
        """

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = get_schema(db=db, branch=branch, node_schema=schema)

        query = await NodeGetListQuery.init(
            db=db,
            schema=node_schema,
            branch=branch,
            filters=filters,
            at=at,
            partial_match=partial_match,
            branch_agnostic=branch_agnostic,
        )
        return await query.count(db=db)

    @classmethod
    async def count_peers(
        cls,
        ids: list[str],
        source_kind: str,
        schema: RelationshipSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        branch_agnostic: bool = False,
    ) -> int:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id="PLACEHOLDER")

        query = await RelationshipGetPeerQuery.init(
            db=db,
            source_ids=ids,
            source_kind=source_kind,
            schema=schema,
            filters=filters,
            rel=rel,
            at=at,
            branch_agnostic=branch_agnostic,
        )
        return await query.count(db=db)

    @classmethod
    async def query_peers(
        cls,
        db: InfrahubDatabase,
        ids: list[str],
        source_kind: str,
        schema: RelationshipSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        branch_agnostic: bool = False,
        fetch_peers: bool = False,
    ) -> list[Relationship]:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id="PLACEHOLDER")

        query = await RelationshipGetPeerQuery.init(
            db=db,
            source_ids=ids,
            source_kind=source_kind,
            schema=schema,
            filters=filters,
            rel=rel,
            offset=offset,
            limit=limit,
            at=at,
            branch_agnostic=branch_agnostic,
        )
        await query.execute(db=db)

        peers_info = list(query.get_peers())
        if not peers_info:
            return []

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            peer_schema = schema.get_peer_schema(db=db, branch=branch)
            schema_branch = db.schema.get_schema_branch(name=branch.name)
            display_label_fields = schema_branch.generate_fields_for_display_label(name=peer_schema.kind)
            if display_label_fields:
                fields = deep_merge_dict(dicta=fields, dictb=display_label_fields)

        if fields and "hfid" in fields:
            peer_schema = schema.get_peer_schema(db=db, branch=branch)
            hfid_fields = peer_schema.generate_fields_for_hfid()
            if hfid_fields:
                fields = deep_merge_dict(dicta=fields, dictb=hfid_fields)

        if fetch_peers:
            peer_ids = [peer.peer_id for peer in peers_info]
            peer_nodes = await cls.get_many(
                db=db, ids=peer_ids, fields=fields, at=at, branch=branch, branch_agnostic=branch_agnostic
            )

        results = []
        for peer in peers_info:
            result = await Relationship(schema=schema, branch=branch, at=at, node_id=peer.source_id).load(
                db=db,
                id=peer.rel_node_id,
                db_id=peer.rel_node_db_id,
                updated_at=peer.updated_at,
                data=peer,
            )
            if fetch_peers:
                await result.set_peer(value=peer_nodes[peer.peer_id])
            results.append(result)

        return results

    @classmethod
    async def count_hierarchy(
        cls,
        id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: NodeSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            filters=filters,
            at=at,
            branch=branch,
        )

        return await query.count(db=db)

    @classmethod
    async def query_hierarchy(
        cls,
        db: InfrahubDatabase,
        id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: NodeSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> dict[str, Any]:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            filters=filters,
            offset=offset,
            limit=limit,
            at=at,
            branch=branch,
        )
        await query.execute(db=db)

        peers_ids = list(query.get_peer_ids())

        if not peers_ids:
            return {}

        hierarchy_schema = node_schema.get_hierarchy_schema(db=db, branch=branch)

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            schema_branch = db.schema.get_schema_branch(name=branch.name)
            display_label_fields = schema_branch.generate_fields_for_display_label(name=hierarchy_schema.kind)
            if display_label_fields:
                fields = deep_merge_dict(dicta=fields, dictb=display_label_fields)

        return await cls.get_many(
            db=db, ids=peers_ids, fields=fields, at=at, branch=branch, include_owner=True, include_source=True
        )

    @overload
    @classmethod
    async def find_object(
        cls,
        db: InfrahubDatabase,
        kind: type[SchemaProtocol],
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        id: str | None = ...,  # pylint: disable=redefined-builtin
        hfid: list[str] | None = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def find_object(
        cls,
        db: InfrahubDatabase,
        kind: str,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        id: str | None = ...,  # pylint: disable=redefined-builtin
        hfid: list[str] | None = ...,
    ) -> Any: ...

    @classmethod
    async def find_object(
        cls,
        db: InfrahubDatabase,
        kind: type[SchemaProtocol] | str,
        at: Timestamp | str | None = None,
        branch: Branch | str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
        hfid: list[str] | None = None,
    ) -> Any:
        if not id and not hfid:
            raise ProcessingError(message="either id or hfid must be provided.")

        if id and is_valid_uuid(id):
            return await cls.get_one(
                db=db,
                kind=kind,
                id=id,
                branch=branch,
                at=at,
                include_owner=True,
                include_source=True,
                raise_on_error=True,
            )

        if hfid:
            return await cls.get_one_by_hfid(
                db=db,
                kind=kind,
                hfid=hfid,
                branch=branch,
                at=at,
                include_owner=True,
                include_source=True,
                raise_on_error=True,
            )

        return await cls.get_one_by_default_filter(
            db=db,
            kind=kind,
            id=id,
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
            raise_on_error=True,
        )

    @overload
    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: type[SchemaProtocol],
        raise_on_error: Literal[False] = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol | None: ...

    @overload
    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: type[SchemaProtocol],
        raise_on_error: Literal[True],
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: type[SchemaProtocol],
        raise_on_error: bool,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: str,
        raise_on_error: bool = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: type[SchemaProtocol] | str,
        raise_on_error: bool = False,
        fields: dict | None = None,
        at: Timestamp | str | None = None,
        branch: Branch | str | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        branch_agnostic: bool = False,
    ) -> Any:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = get_schema(db=db, branch=branch, node_schema=kind)
        kind_str = node_schema.kind

        if not node_schema.default_filter:
            raise NodeNotFoundError(branch_name=branch.name, node_type=kind_str, identifier=id)

        items = await NodeManager.query(
            db=db,
            schema=node_schema,
            fields=fields,
            limit=2,
            filters={node_schema.default_filter: id},
            branch=branch,
            at=at,
            include_owner=include_owner,
            include_source=include_source,
            prefetch_relationships=prefetch_relationships,
            account=account,
            branch_agnostic=branch_agnostic,
        )

        if len(items) > 1:
            raise NodeNotFoundError(
                branch_name=branch.name,
                node_type=kind_str,
                identifier=id,
                message=f"Unable to find node {id!r}, {len(items)} nodes returned, expected 1",
            )

        if items:
            return items[0]
        if not raise_on_error:
            return None

        raise NodeNotFoundError(
            branch_name=branch.name,
            node_type=kind_str,
            identifier=id,
        )

    @overload
    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: type[SchemaProtocol],
        raise_on_error: Literal[False] = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
    ) -> SchemaProtocol | None: ...

    @overload
    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: type[SchemaProtocol],
        raise_on_error: Literal[True],
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: type[SchemaProtocol],
        raise_on_error: bool,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: str,
        raise_on_error: Literal[True],
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @overload
    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: str,
        raise_on_error: bool = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @classmethod
    async def get_one_by_hfid(
        cls,
        db: InfrahubDatabase,
        hfid: list[str],
        kind: type[SchemaProtocol] | str,
        raise_on_error: bool = False,
        fields: dict | None = None,
        at: Timestamp | str | None = None,
        branch: Branch | str | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        branch_agnostic: bool = False,
    ) -> Any:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = get_schema(db=db, branch=branch, node_schema=kind)
        kind_str = node_schema.kind

        hfid_str = " :: ".join(hfid)

        if not node_schema.human_friendly_id or len(node_schema.human_friendly_id) != len(hfid):
            raise NodeNotFoundError(branch_name=branch.name, node_type=kind_str, identifier=hfid_str)

        filters = {}
        for key, item in zip(node_schema.human_friendly_id, hfid):
            path = node_schema.parse_schema_path(path=key, schema=registry.schema.get_schema_branch(name=branch.name))

            if path.is_type_relationship:
                rel_schema = path.related_schema
                # Keep the relationship attribute path and parse it
                path = rel_schema.parse_schema_path(
                    path=key.split("__", maxsplit=1)[1], schema=registry.schema.get_schema_branch(name=branch.name)
                )

            filters[key] = path.attribute_schema.get_class().deserialize_from_string(item)

        items = await NodeManager.query(
            db=db,
            schema=node_schema,
            fields=fields,
            limit=2,
            filters=filters,
            branch=branch,
            at=at,
            include_owner=include_owner,
            include_source=include_source,
            prefetch_relationships=prefetch_relationships,
            account=account,
            branch_agnostic=branch_agnostic,
        )

        if len(items) < 1:
            if raise_on_error:
                raise NodeNotFoundError(branch_name=branch.name, node_type=kind_str, identifier=hfid_str)
            return None

        if len(items) > 1:
            raise NodeNotFoundError(
                branch_name=branch.name,
                node_type=kind_str,
                identifier=hfid_str,
                message=f"Unable to find node {hfid_str!r}, {len(items)} nodes returned, expected 1",
            )

        return items[0]

    @overload
    @classmethod
    async def get_one_by_id_or_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: type[SchemaProtocol],
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one_by_id_or_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: str,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @classmethod
    async def get_one_by_id_or_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        kind: str | type[SchemaProtocol],
        fields: dict | None = None,
        at: Timestamp | str | None = None,
        branch: Branch | str | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        branch_agnostic: bool = False,
    ) -> Any:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node = await cls.get_one(
            id=id,
            fields=fields,
            at=at,
            branch=branch,
            include_owner=include_owner,
            include_source=include_source,
            db=db,
            prefetch_relationships=prefetch_relationships,
            account=account,
            branch_agnostic=branch_agnostic,
        )
        if node:
            return node

        node = await cls.get_one_by_default_filter(
            db=db,
            id=id,
            kind=kind,
            fields=fields,
            at=at,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            prefetch_relationships=prefetch_relationships,
            account=account,
            branch_agnostic=branch_agnostic,
        )
        if not node:
            raise NodeNotFoundError(branch_name=branch.name, node_type=kind, identifier=id)
        return node

    @overload
    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: type[SchemaProtocol],
        raise_on_error: Literal[False] = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol | None: ...

    @overload
    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: type[SchemaProtocol],
        raise_on_error: Literal[True],
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: type[SchemaProtocol],
        raise_on_error: bool,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> SchemaProtocol: ...

    @overload
    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: str,
        raise_on_error: bool = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @overload
    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: Literal[None] = ...,
        raise_on_error: bool = ...,
        fields: dict | None = ...,
        at: Timestamp | str | None = ...,
        branch: Branch | str | None = ...,
        include_source: bool = ...,
        include_owner: bool = ...,
        prefetch_relationships: bool = ...,
        account=...,
        branch_agnostic: bool = ...,
    ) -> Any: ...

    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        kind: str | type[SchemaProtocol] | None = None,
        raise_on_error: bool = False,
        fields: dict | None = None,
        at: Timestamp | str | None = None,
        branch: Branch | str | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        branch_agnostic: bool = False,
    ) -> Optional[Any]:
        """Return one node based on its ID."""
        branch = await registry.get_branch(branch=branch, db=db)

        result = await cls.get_many(
            ids=[id],
            fields=fields,
            at=at,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            prefetch_relationships=prefetch_relationships,
            db=db,
            branch_agnostic=branch_agnostic,
        )

        if not result:
            if raise_on_error:
                raise NodeNotFoundError(branch_name=branch.name, node_type=kind, identifier=id)
            return None

        node = result[id]
        node_schema = node.get_schema()

        kind_validation = None
        if kind:
            node_schema_validation = get_schema(db=db, branch=branch, node_schema=kind)
            kind_validation = node_schema_validation.kind

        # Temporary list of exception to the validation of the kind
        kind_validation_exceptions = [
            ("CoreChangeThread", "CoreObjectThread"),  # issue/3318
        ]

        if kind_validation and (
            node_schema.kind != kind_validation and kind_validation not in node_schema.inherit_from
        ):
            for item in kind_validation_exceptions:
                if item[0] == kind_validation and item[1] == node.get_kind():
                    return node

            raise NodeNotFoundError(
                branch_name=branch.name,
                node_type=kind_validation,
                identifier=id,
                message=f"Node with id {id} exists, but it is a {node.get_kind()}, not {kind_validation}",
            )

        return node

    @classmethod
    async def get_many(  # pylint: disable=too-many-branches,too-many-statements
        cls,
        db: InfrahubDatabase,
        ids: list[str],
        fields: Optional[dict] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        branch_agnostic: bool = False,
    ) -> dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(
            db=db, ids=ids, branch=branch, account=account, at=at, branch_agnostic=branch_agnostic
        )
        await query.execute(db=db)
        nodes_info_by_id: dict[str, NodeToProcess] = {node.node_uuid: node async for node in query.get_nodes(db=db)}
        profile_ids_by_node_id = query.get_profile_ids_by_node_id()
        all_profile_ids = reduce(
            lambda all_ids, these_ids: all_ids | set(these_ids), profile_ids_by_node_id.values(), set()
        )

        if fields and all_profile_ids:
            if "profile_priority" not in fields:
                fields["profile_priority"] = {}
            if "value" not in fields["profile_priority"]:
                fields["profile_priority"]["value"] = None

        # Query list of all Attributes
        query = await NodeListGetAttributeQuery.init(
            db=db,
            ids=list(nodes_info_by_id.keys()) + list(all_profile_ids),
            fields=fields,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            at=at,
            branch_agnostic=branch_agnostic,
        )
        await query.execute(db=db)
        all_node_attributes = query.get_attributes_group_by_node()
        profile_attributes: dict[str, dict[str, AttributeFromDB]] = {}
        node_attributes: dict[str, dict[str, AttributeFromDB]] = {}
        for node_id, attribute_dict in all_node_attributes.items():
            if node_id in all_profile_ids:
                profile_attributes[node_id] = attribute_dict
            else:
                node_attributes[node_id] = attribute_dict
        profile_index = ProfileAttributeIndex(
            profile_attributes_id_map=profile_attributes, profile_ids_by_node_id=profile_ids_by_node_id
        )

        # if prefetch_relationships is enabled
        # Query all the peers associated with all nodes at once.
        peers_per_node: dict[str, dict[str, list[str]]] = {}
        peers: dict[str, Node] = {}
        if prefetch_relationships:
            query = await NodeListGetRelationshipsQuery.init(
                db=db, ids=ids, branch=branch, at=at, branch_agnostic=branch_agnostic
            )
            await query.execute(db=db)
            peers_per_node = query.get_peers_group_by_node()
            peer_ids = []

            for node_data in peers_per_node.values():
                for node_peers in node_data.values():
                    peer_ids.extend(node_peers)

            # query the peers that are not already part of the main list
            peer_ids = list(set(peer_ids) - set(ids))
            peers = await cls.get_many(
                ids=peer_ids,
                branch=branch,
                at=at,
                db=db,
                include_owner=include_owner,
                include_source=include_source,
            )

        nodes: dict[str, Node] = {}

        for node_id in ids:  # pylint: disable=too-many-nested-blocks
            if node_id not in nodes_info_by_id:
                continue

            node = nodes_info_by_id[node_id]
            new_node_data: dict[str, Union[str, AttributeFromDB]] = {
                "db_id": node.node_id,
                "id": node_id,
                "updated_at": node.updated_at,
            }

            if not node.schema:
                raise SchemaNotFoundError(
                    branch_name=branch.name,
                    identifier=node_id,
                    message=f"Unable to find the Schema associated with {node_id}, {node.labels}",
                )

            # --------------------------------------------------------
            # Attributes
            # --------------------------------------------------------
            if node_id in node_attributes:
                for attr_name, attr in node_attributes[node_id].attrs.items():
                    new_node_data[attr_name] = attr

            new_node_data_with_profile_overrides = profile_index.apply_profiles(new_node_data)
            node_class = identify_node_class(node=node)
            node_branch = await registry.get_branch(db=db, branch=node.branch)
            item = await node_class.init(schema=node.schema, branch=node_branch, at=at, db=db)
            await item.load(**new_node_data_with_profile_overrides, db=db)

            nodes[node_id] = item

        # --------------------------------------------------------
        # Relationships
        # --------------------------------------------------------
        if prefetch_relationships:
            for node_id, node in nodes.items():
                if node_id not in peers_per_node.keys():
                    continue

                for rel_schema in node._schema.relationships:
                    direction_identifier = f"{rel_schema.direction.value}::{rel_schema.identifier}"
                    if direction_identifier in peers_per_node[node_id]:
                        rel_peers = [
                            peers.get(id, None) or nodes.get(id) for id in peers_per_node[node_id][direction_identifier]
                        ]
                        rel_manager: RelationshipManager = getattr(node, rel_schema.name)
                        if rel_schema.cardinality == "one" and not len(rel_peers) == 1:
                            raise ValueError("Only one relationship expected")

                        rel_manager.has_fetched_relationships = True
                        await rel_manager.update(db=db, data=rel_peers)

        return nodes

    @classmethod
    async def delete(
        cls,
        db: InfrahubDatabase,
        nodes: list[Node],
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> list[Any]:
        """Returns list of deleted nodes because of cascading deletes"""
        branch = await registry.get_branch(branch=branch, db=db)
        node_delete_validator = NodeDeleteValidator(db=db, branch=branch)
        ids_to_delete = await node_delete_validator.get_ids_to_delete(nodes=nodes, at=at)
        node_ids = {node.get_id() for node in nodes}
        missing_ids_to_delete = ids_to_delete - node_ids
        if missing_ids_to_delete:
            node_map = await cls.get_many(db=db, ids=list(missing_ids_to_delete), branch=branch, at=at)
            nodes += list(node_map.values())
        deleted_nodes = []
        for node in nodes:
            await node.delete(db=db, at=at)
            deleted_nodes.append(node)

        return deleted_nodes


registry.manager = NodeManager
