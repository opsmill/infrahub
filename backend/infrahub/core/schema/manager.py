from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cachetools import LRUCache
from infrahub_sdk.schema import BranchSchema as SDKBranchSchema

from infrahub import lock
from infrahub.core.constants import (
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    PROFILES_RELATIONSHIP_NAME,
    SYSTEM_USER_ID,
    MetadataOptions,
)
from infrahub.core.manager import NodeManager
from infrahub.core.models import (
    HashableModelDiff,
    SchemaBranchDiff,
    SchemaDiff,
)
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    RelationshipSchema,
    SchemaRoot,
    TemplateSchema,
)
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import parse_node_kind
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

from .constants import IGNORE_FOR_NODE
from .queries import SchemaSummary, SchemaSummaryQuery
from .schema_branch import SchemaBranch

log = get_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class SchemaManager(NodeManager):
    _virtual_relationship_names: set[str] = {OBJECT_TEMPLATE_RELATIONSHIP_NAME, PROFILES_RELATIONSHIP_NAME}

    def __init__(self) -> None:
        self._cache: dict[int, Any] = {}
        self._branches: dict[str, SchemaBranch] = {}
        self._branch_hash_by_name: dict[str, str] = {}
        self._sdk_branches: LRUCache[str, SDKBranchSchema] = LRUCache(maxsize=10)

    @classmethod
    def _is_virtual_relationship(cls, name: str) -> bool:
        """Virtual relationships exist only in-memory (added by SchemaBranch.process) and are never persisted."""
        return name in cls._virtual_relationship_names

    def _get_from_cache(self, key: int) -> Any:
        return self._cache[key]

    def set(self, name: str, schema: NodeSchema | GenericSchema, branch: str | None = None) -> int:
        branch = branch or registry.default_branch

        if branch not in self._branches:
            self._branches[branch] = SchemaBranch(cache=self._cache, name=branch)

        self._branches[branch].set(name=name, schema=schema)

        return hash(self._branches[branch])

    def has(self, name: str, branch: Branch | str | None = None) -> bool:
        try:
            self.get(name=name, branch=branch, duplicate=False)
            return True
        except SchemaNotFoundError:
            return False

    def get(
        self,
        name: str,
        branch: Branch | str | None = None,
        duplicate: bool = True,
        check_branch_only: bool = False,
    ) -> MainSchemaTypes:
        # For now we assume that all branches are present, will see how we need to pull new branches later.
        check_branch_only = check_branch_only and bool(branch)
        branch = registry.get_branch_from_registry(branch=branch)

        if branch.name in self._branches:
            try:
                return self._branches[branch.name].get(name=name, duplicate=duplicate)
            except SchemaNotFoundError:
                pass

        if check_branch_only:
            raise SchemaNotFoundError(
                branch_name=branch.name, identifier=name, message=f"Unable to find the schema {name!r} in the registry"
            )

        default_branch = registry.default_branch
        return self._branches[default_branch].get(name=name, duplicate=duplicate)

    def get_node_schema(self, name: str, branch: Branch | str | None = None, duplicate: bool = True) -> NodeSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, NodeSchema):
            return schema

        raise ValueError("The selected node is not of type NodeSchema")

    def get_generic_schema(
        self, name: str, branch: Branch | str | None = None, duplicate: bool = True
    ) -> GenericSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, GenericSchema):
            return schema

        raise ValueError("The selected node is not of type GenericSchema")

    def get_profile_schema(
        self, name: str, branch: Branch | str | None = None, duplicate: bool = True
    ) -> ProfileSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, ProfileSchema):
            return schema

        raise ValueError("The selected node is not of type ProfileSchema")

    def get_template_schema(
        self, name: str, branch: Branch | str | None = None, duplicate: bool = True
    ) -> TemplateSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, TemplateSchema):
            return schema

        raise ValueError("The selected node is not of type TemplateSchema")

    def get_full(self, branch: Branch | str | None = None, duplicate: bool = True) -> dict[str, MainSchemaTypes]:
        branch = registry.get_branch_from_registry(branch=branch)

        branch_name = None
        if branch.name in self._branches:
            branch_name = branch.name
        else:
            branch_name = registry.default_branch

        return self._branches[branch_name].get_all(duplicate=duplicate)

    async def get_full_safe(self, branch: Branch | str | None = None) -> dict[str, MainSchemaTypes]:
        await lock.registry.local_schema_wait()

        return self.get_full(branch=branch)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name in self._branches:
            return self._branches[name]

        self.set_schema_branch(name, schema=SchemaBranch(cache=self._cache, name=name))
        return self._branches[name]

    def get_sdk_schema_branch(self, name: str) -> SDKBranchSchema:
        schema_hash = self._branch_hash_by_name[name]
        branch_schema = self._sdk_branches.get(schema_hash)
        if not branch_schema:
            self._sdk_branches[schema_hash] = SDKBranchSchema.from_api_response(
                data=self._branches[name].to_dict_api_schema_object()
            )

        return self._sdk_branches[schema_hash]

    def set_schema_branch(self, name: str, schema: SchemaBranch) -> None:
        schema.name = name
        self._branches[name] = schema
        self._branch_hash_by_name[name] = schema.get_hash()

    def has_schema_branch(self, name: str) -> bool:
        return name in self._branches

    def process_schema_branch(self, name: str) -> None:
        schema_branch = self.get_schema_branch(name=name)
        schema_branch.process()

    async def update_schema_branch(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
        diff: SchemaDiff | None = None,
        limit: list[str] | None = None,
        update_db: bool = True,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        updated_schema = None
        if update_db:
            if diff:
                schema_diff = await self.update_schema_to_db(
                    schema=schema, db=db, branch=branch, diff=diff, at=at, user_id=user_id
                )
            else:
                await self.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit, at=at, user_id=user_id)
                # After updating the schema into the db
                # we need to pull a fresh version because some default value are managed/generated within the node object
                schema_diff = None
                if limit:
                    schema_diff = SchemaBranchDiff(
                        added_nodes=[name for name in list(schema.nodes.keys()) if name in limit],
                        added_generics=[name for name in list(schema.generics.keys()) if name in limit],
                    )

            updated_schema = await self.load_schema_from_db(
                db=db, branch=branch, schema=schema, schema_diff=schema_diff, at=at
            )

        self.set_schema_branch(name=branch.name, schema=updated_schema or schema)

    def register_schema(self, schema: SchemaRoot, branch: str | None = None) -> SchemaBranch:
        """Register all nodes, generics & groups from a SchemaRoot object into the registry."""
        branch = branch or registry.default_branch
        schema_branch = self.get_schema_branch(name=branch)
        schema_branch.load_schema(schema=schema)
        schema_branch.process()
        return schema_branch

    async def update_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        diff: SchemaDiff,
        user_id: str,
        at: Timestamp,
        branch: Branch | str | None = None,
    ) -> SchemaBranchDiff:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""
        branch = await registry.get_branch(branch=branch, db=db)

        upsert_kinds = list(diff.added.keys()) + [k for k, d in diff.changed.items() if not d]
        upsert_schemas: list[NodeSchema | GenericSchema] = []
        for kind in upsert_kinds:
            one_schema = schema.get(name=kind, duplicate=False)
            # SchemaDiff excludes Profile/Template, so only NodeSchema/GenericSchema can appear here
            # we also don't save Profile/Template schemas to the database, they're always generated
            if isinstance(one_schema, (NodeSchema, GenericSchema)):
                upsert_schemas.append(one_schema)
        schema_summary_map = await self._get_existing_schema_summary_map(
            schemas=upsert_schemas, branch=branch, db=db, at=at
        )
        existing_children = await self._prefetch_existing_children(
            schemas=upsert_schemas, schema_summary_map=schema_summary_map, branch=branch, db=db
        )

        added_nodes: list[str] = []
        added_generics: list[str] = []
        changed_nodes: list[str] = []
        changed_generics: list[str] = []
        for schema_kind in diff.added.keys():
            one_schema = schema.get(name=schema_kind, duplicate=False)
            db_node, info = schema_summary_map.get(one_schema.kind, (None, None))
            node = await self._upsert_node_to_db(
                node=one_schema,
                existing_db_node=db_node,
                existing_summary=info,
                existing_fields=existing_children,
                branch=branch,
                db=db,
                at=at,
                user_id=user_id,
            )
            schema.set(name=schema_kind, schema=node)
            # The caller's diff said this kind was "added", but if a row already existed on the DB
            # then this is actually "changed"
            target_node_bucket = added_nodes if db_node is None else changed_nodes
            target_generic_bucket = added_generics if db_node is None else changed_generics
            if one_schema.is_node_schema:
                target_node_bucket.append(schema_kind)
            else:
                target_generic_bucket.append(schema_kind)

        for schema_kind, schema_diff in diff.changed.items():
            one_schema = schema.get(name=schema_kind, duplicate=False)
            if schema_diff:
                node = await self.update_node_in_db_based_on_diff(
                    node=one_schema, branch=branch, db=db, diff=schema_diff, at=at, user_id=user_id
                )
            else:
                db_node, info = schema_summary_map.get(one_schema.kind, (None, None))
                node = await self._upsert_node_to_db(
                    node=one_schema,
                    existing_db_node=db_node,
                    existing_summary=info,
                    existing_fields=existing_children,
                    branch=branch,
                    db=db,
                    at=at,
                    user_id=user_id,
                )
            schema.set(name=schema_kind, schema=node)
            if one_schema.is_node_schema:
                changed_nodes.append(schema_kind)
            else:
                changed_generics.append(schema_kind)

        removed_nodes = []
        removed_generics = []
        for schema_kind in diff.removed.keys():
            one_schema = schema.get(name=schema_kind, duplicate=False)
            node = await self.delete_node_in_db(node=one_schema, branch=branch, db=db, at=at, user_id=user_id)
            schema.delete(name=schema_kind)
            if one_schema.is_node_schema:
                removed_nodes.append(schema_kind)
            else:
                removed_generics.append(schema_kind)

        return SchemaBranchDiff(
            added_nodes=added_nodes,
            added_generics=added_generics,
            changed_nodes=changed_nodes,
            changed_generics=changed_generics,
            removed_nodes=removed_nodes,
            removed_generics=removed_generics,
        )

    async def load_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
        limit: list[str] | None = None,
        user_id: str = SYSTEM_USER_ID,
        at: Timestamp | None = None,
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""
        at = Timestamp(at)
        branch = await registry.get_branch(branch=branch, db=db)

        schemas: list[NodeSchema | GenericSchema] = []
        for schema_kind in schema.node_names + schema.generic_names_without_templates:
            if limit and schema_kind not in limit:
                continue
            one_schema = schema.get(name=schema_kind, duplicate=False)
            if isinstance(one_schema, (NodeSchema, GenericSchema)):
                schemas.append(one_schema)

        schema_summary_map = await self._get_existing_schema_summary_map(schemas=schemas, branch=branch, db=db, at=at)
        existing_children = await self._prefetch_existing_children(
            schemas=schemas, schema_summary_map=schema_summary_map, branch=branch, db=db
        )

        for one_schema in schemas:
            db_node, info = schema_summary_map.get(one_schema.kind, (None, None))
            node = await self._upsert_node_to_db(
                node=one_schema,
                existing_db_node=db_node,
                existing_fields=existing_children,
                existing_summary=info,
                branch=branch,
                db=db,
                at=at,
                user_id=user_id,
            )
            schema.set(name=one_schema.kind, schema=node)

    async def _get_existing_schema_summary_map(
        self,
        schemas: Sequence[NodeSchema | GenericSchema],
        branch: Branch,
        db: InfrahubDatabase,
        at: Timestamp | None = None,
    ) -> dict[str, tuple[Node, SchemaSummary]]:
        """Retrieve the current database object (Node) and SchemaSummary for all ``schemas``

        Returns a dict keyed by ``kind`` (``namespace + name``) mapping to a tuple of:
        - the current ``Node`` for the schema object, if it exists
        - ``SchemaSummary`` linking each schema kind to its ID and its ID-less fields to their
        IDs if they already exist

        Schemas that do not exist on the database will not be in the returned dictionary.

        Raises:
            ValueError: When a member of `schemas` has a different type than its counterpart
                in the database. For example, incoming NodeScheam versus existing GenericSchema.

        """
        if not schemas:
            return {}

        # both filters are necessary to account for renamed schemas
        kind_filter = [(one_schema.namespace, one_schema.name) for one_schema in schemas]
        uuid_filter = [one_schema.id for one_schema in schemas if one_schema.id]
        # only retrieve fields for a schema if the field is being added
        # (it has no ID set b/c it has not come from the database)
        attribute_names = list(
            {attr.name for one_schema in schemas for attr in one_schema.local_attributes if attr.id is None}
        )
        relationship_names = list(
            {
                rel.name
                for one_schema in schemas
                for rel in one_schema.local_relationships
                if rel.id is None and not self._is_virtual_relationship(rel.name)
            }
        )
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=branch,
            at=at,
            kind_filter=kind_filter,
            uuid_filter=uuid_filter,
            attribute_names=attribute_names,
            relationship_names=relationship_names,
        )
        await query.execute(db=db)
        summary_index = query.get_summaries()

        summaries_by_kind: dict[str, SchemaSummary] = {}
        for one_schema in schemas:
            # Try to match by UUID first to make sure a kind update is handled correctly
            summary: SchemaSummary | None = None
            if one_schema.id:
                summary = summary_index.get_summary_by_uuid(uuid=one_schema.id)
            if summary is None:
                summary = summary_index.get_summary_by_kind(kind=one_schema.kind)
            if summary is None:
                continue

            # unlikely case, but better to prevent it for sure
            schema_is_generic = isinstance(one_schema, GenericSchema)
            if summary.is_generic != schema_is_generic:
                input_type = "GenericSchema" if schema_is_generic else "NodeSchema"
                db_type = "SchemaGeneric" if summary.is_generic else "SchemaNode"
                raise ValueError(
                    f"Schema kind {one_schema.kind!r} on branch {branch.name!r} has a type mismatch: "
                    f"input is a {input_type} but the existing DB row is a {db_type} (uuid={summary.uuid})."
                )
            summaries_by_kind[one_schema.kind] = summary

        if not summaries_by_kind:
            return {}

        nodes_by_id = await self.get_many(
            ids=[summary.uuid for summary in summaries_by_kind.values()],
            db=db,
            branch=branch,
            at=at,
            prefetch_relationships=True,
        )
        result: dict[str, tuple[Node, SchemaSummary]] = {}
        for kind, summary in summaries_by_kind.items():
            schema_object = nodes_by_id.get(summary.uuid)
            if schema_object is None:
                continue
            result[kind] = (schema_object, summary)
        return result

    async def _prefetch_existing_children(
        self,
        schemas: Sequence[NodeSchema | GenericSchema],
        schema_summary_map: dict[str, tuple[Node, SchemaSummary]],
        branch: Branch,
        db: InfrahubDatabase,
    ) -> dict[str, Node]:
        """Bulk-fetch the SchemaAttribute / SchemaRelationship Nodes the update path will touch."""
        all_ids: set[str] = set()
        for one_schema in schemas:
            resolved = schema_summary_map.get(one_schema.kind)
            # schema does not exist on the database yet, so nothing to fetch
            if resolved is None:
                continue
            _, summary = resolved
            for attr in one_schema.local_attributes:
                # prefer ID from the database over incoming ID
                child_id = summary.attributes.get(attr.name) or attr.id
                if child_id:
                    all_ids.add(child_id)
            for rel in one_schema.local_relationships:
                if self._is_virtual_relationship(rel.name):
                    continue
                child_id = summary.relationships.get(rel.name) or rel.id
                if child_id:
                    all_ids.add(child_id)

        if not all_ids:
            return {}
        return await self.get_many(ids=list(all_ids), db=db, branch=branch)

    async def create_node_in_db(
        self,
        node: NodeSchema | GenericSchema,
        db: InfrahubDatabase,
        user_id: str,
        at: Timestamp,
        branch: Branch | str | None = None,
    ) -> NodeSchema | GenericSchema:
        """Insert a new schema node with its attributes and relationships.

        Always adds the schema. Does not check if it already exists.
        """
        branch = await registry.get_branch(branch=branch, db=db)
        return await self._create_node_in_db(node=node, branch=branch, db=db, at=at, user_id=user_id)

    async def _upsert_node_to_db(
        self,
        node: NodeSchema | GenericSchema,
        db: InfrahubDatabase,
        user_id: str,
        at: Timestamp,
        existing_db_node: Node | None,
        existing_summary: SchemaSummary | None,
        existing_fields: dict[str, Node],
        branch: Branch,
    ) -> NodeSchema | GenericSchema:
        """Insert or update a schema node based on a pre-resolved DB Node."""
        if existing_db_node is None:
            return await self._create_node_in_db(node=node, branch=branch, db=db, at=at, user_id=user_id)
        return await self._update_existing_node_in_db(
            schema=node,
            existing_schema_object=existing_db_node,
            existing_summary=existing_summary,
            existing_fields=existing_fields,
            branch=branch,
            db=db,
            at=at,
            user_id=user_id,
        )

    async def _create_node_in_db(
        self,
        node: NodeSchema | GenericSchema,
        db: InfrahubDatabase,
        user_id: str,
        at: Timestamp,
        branch: Branch,
    ) -> NodeSchema | GenericSchema:
        """Insert a new schema node with its attributes and relationships."""
        node_type = "SchemaNode"
        if isinstance(node, GenericSchema):
            node_type = "SchemaGeneric"

        node_schema = self.get_node_schema(name=node_type, branch=branch, duplicate=False)
        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch, duplicate=False)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch, duplicate=False)

        # Duplicate the node in order to store the IDs after inserting them in the database
        new_node = node.duplicate()

        # Create the node first
        schema_dict = node.model_dump(exclude={"id", "state", "filters", "relationships", "attributes"})
        obj = await Node.init(schema=node_schema, branch=branch, db=db)
        await obj.new(**schema_dict, db=db)
        await obj.save(db=db, at=at, user_id=user_id)
        new_node.id = obj.id

        # Then create the Attributes and the relationships
        if isinstance(node, NodeSchema | GenericSchema):
            new_node.relationships = []
            new_node.attributes = []

            for attribute in node.attributes:
                if attribute.inherited is False:
                    new_attr = await self.create_attribute_in_db(
                        schema=attribute_schema,
                        item=attribute,
                        parent=obj,
                        branch=branch,
                        db=db,
                        at=at,
                        user_id=user_id,
                    )
                else:
                    new_attr = attribute.duplicate()
                new_node.attributes.append(new_attr)

            for relationship in node.relationships:
                if self._is_virtual_relationship(relationship.name):
                    new_node.relationships.append(relationship.duplicate())
                    continue
                if relationship.inherited is False:
                    new_rel = await self.create_relationship_in_db(
                        schema=relationship_schema,
                        item=relationship,
                        parent=obj,
                        branch=branch,
                        db=db,
                        at=at,
                        user_id=user_id,
                    )
                else:
                    new_rel = relationship.duplicate()
                new_node.relationships.append(new_rel)

        # Save back the node with the newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def _update_existing_node_in_db(
        self,
        db: InfrahubDatabase,
        schema: NodeSchema | GenericSchema,
        existing_schema_object: Node,
        existing_summary: SchemaSummary | None,
        existing_fields: dict[str, Node],
        user_id: str,
        at: Timestamp,
        branch: Branch,
    ) -> NodeSchema | GenericSchema:
        """Update a Node with its attributes and its relationships in the database.

        The returned schema will carry ``existing_schema_object.id`` regardless of what was on the
        input ``schema``.

        ``existing_summary`` (when supplied) names the attributes and relationships already on
        ``existing_schema_object`` in the DB, keyed by name. Each input field is resolved by
        preferring the DB-known uuid for that name, to prevent duplicate fields

        ``existing_fields`` is a pre-fetched ``{uuid: Node}`` dict for every field this
        update path will touch

        Raises:
            SchemaNotFoundError: When no existing schema node matches the given node id on the branch.

        """
        schema_dict = schema.model_dump(exclude=IGNORE_FOR_NODE)
        for key, value in schema_dict.items():
            if obj_attr := getattr(existing_schema_object, key, None):
                obj_attr.value = value

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        new_node = schema.duplicate()
        new_node.id = existing_schema_object.id

        existing_attrs = existing_summary.attributes if existing_summary else {}
        existing_rels = existing_summary.relationships if existing_summary else {}

        # For each local attr/rel, resolve the DB uuid to update (input id wins; fall back to
        # name-based lookup from existing_info). Items still unresolved will be created.
        attr_resolved_ids: dict[str, str] = {}
        for attribute in schema.local_attributes:
            resolved = attribute.id or existing_attrs.get(attribute.name)
            if resolved:
                attr_resolved_ids[attribute.name] = resolved

        rel_resolved_ids: dict[str, str] = {}
        for relationship in schema.local_relationships:
            if self._is_virtual_relationship(relationship.name):
                continue
            resolved = relationship.id or existing_rels.get(relationship.name)
            if resolved:
                rel_resolved_ids[relationship.name] = resolved

        # Update the parent's link lists using the resolved ids
        await existing_schema_object.get_relationship("attributes").update(
            db=db, data=list(attr_resolved_ids.values()), at=at
        )
        await existing_schema_object.get_relationship("relationships").update(
            db=db, data=list(rel_resolved_ids.values()), at=at
        )
        await existing_schema_object.save(db=db, at=at, user_id=user_id)

        new_attr_by_name = {a.name: a for a in new_node.local_attributes}
        new_rel_by_name = {r.name: r for r in new_node.local_relationships}

        for attribute in schema.local_attributes:
            resolved_id = attr_resolved_ids.get(attribute.name)
            if resolved_id and resolved_id in existing_fields:
                await self.update_attribute_in_db(
                    item=attribute, attr=existing_fields[resolved_id], db=db, at=at, user_id=user_id
                )
                new_attr_by_name[attribute.name].id = resolved_id
            elif not resolved_id:
                new_db_attr = await self.create_attribute_in_db(
                    schema=attribute_schema,
                    item=attribute,
                    branch=branch,
                    db=db,
                    parent=existing_schema_object,
                    at=at,
                    user_id=user_id,
                )
                new_attr_by_name[attribute.name].id = new_db_attr.id

        for relationship in schema.local_relationships:
            if self._is_virtual_relationship(relationship.name):
                continue
            resolved_id = rel_resolved_ids.get(relationship.name)
            if resolved_id and resolved_id in existing_fields:
                await self.update_relationship_in_db(
                    item=relationship, rel=existing_fields[resolved_id], db=db, at=at, user_id=user_id
                )
                new_rel_by_name[relationship.name].id = resolved_id
            elif not resolved_id:
                new_db_rel = await self.create_relationship_in_db(
                    schema=relationship_schema,
                    item=relationship,
                    branch=branch,
                    db=db,
                    parent=existing_schema_object,
                    at=at,
                    user_id=user_id,
                )
                new_rel_by_name[relationship.name].id = new_db_rel.id

        # Save back the node with the resolved/created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db_based_on_diff(
        self,
        db: InfrahubDatabase,
        diff: HashableModelDiff,
        node: NodeSchema | GenericSchema,
        user_id: str,
        at: Timestamp,
        branch: Branch | str | None = None,
    ) -> NodeSchema | GenericSchema:
        """Update a Node with its attributes and its relationships in the database based on a HashableModelDiff.

        Raises:
            SchemaNotFoundError: When no existing schema node matches the given node id on the branch.

        """
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.get_id(),
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        properties_to_update = set(list(diff.added.keys()) + list(diff.changed.keys())) - IGNORE_FOR_NODE

        if properties_to_update:
            schema_dict = node.model_dump(exclude=IGNORE_FOR_NODE)
            for key, value in schema_dict.items():
                getattr(obj, key).value = value

        new_node = node.duplicate()
        diff_attributes = diff.changed.get("attributes")
        diff_relationships = diff.changed.get("relationships")

        items = await self._resolve_diff_fields(
            db=db, branch=branch, node=node, diff_attributes=diff_attributes, diff_relationships=diff_relationships
        )

        if diff_attributes:
            await obj.get_relationship("attributes").update(
                db=db, data=[item.id for item in node.local_attributes if item.id], at=at
            )

        if diff_relationships:
            await obj.get_relationship("relationships").update(
                db=db,
                data=[
                    item.id
                    for item in node.local_relationships
                    if item.id and not self._is_virtual_relationship(item.name)
                ],
                at=at,
            )

        await obj.save(db=db, at=at, user_id=user_id)

        await self._apply_diff_field_changes(
            db=db,
            branch=branch,
            node=node,
            new_node=new_node,
            obj=obj,
            items=items,
            diff_attributes=diff_attributes,
            diff_relationships=diff_relationships,
            at=at,
            user_id=user_id,
        )

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def _resolve_diff_fields(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node: NodeSchema | GenericSchema,
        diff_attributes: HashableModelDiff | None,
        diff_relationships: HashableModelDiff | None,
    ) -> dict[str, Node]:
        """Fetch DB nodes for attributes and relationships referenced in the schema diff."""
        attrs_rels_to_update: set[str] = set()
        if diff_attributes:
            attrs_rels_to_update.update(set(diff_attributes.added.keys()))
            attrs_rels_to_update.update(set(diff_attributes.changed.keys()))
            attrs_rels_to_update.update(set(diff_attributes.removed.keys()))
        if diff_relationships:
            attrs_rels_to_update.update(set(diff_relationships.added.keys()))
            attrs_rels_to_update.update(set(diff_relationships.changed.keys()))
            attrs_rels_to_update.update(set(diff_relationships.removed.keys()))

        item_ids = set()
        item_names = set()
        for field in node.local_attributes + node.local_relationships:
            if field.name not in attrs_rels_to_update:
                continue
            if field.id:
                item_ids.add(field.id)
                item_names.add(field.name)
        missing_field_names = list(attrs_rels_to_update - item_names)

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        items: dict[str, Node] = {}
        if item_ids:
            items = await self.get_many(
                ids=list(item_ids),
                db=db,
                branch=branch,
                include_metadata=MetadataOptions.LINKED_NODES,
            )
        if missing_field_names:
            missing_attrs = await self.query(
                db=db,
                branch=branch,
                schema=attribute_schema,
                filters={"name__values": missing_field_names, "node__id": node.id},
                include_metadata=MetadataOptions.LINKED_NODES,
            )
            missing_rels = await self.query(
                db=db,
                branch=branch,
                schema=relationship_schema,
                filters={"name__values": missing_field_names, "node__id": node.id},
                include_metadata=MetadataOptions.LINKED_NODES,
            )
            items.update({field.id: field for field in missing_attrs + missing_rels})

        return items

    async def _apply_diff_field_changes(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node: NodeSchema | GenericSchema,
        new_node: NodeSchema | GenericSchema,
        obj: Node,
        items: dict[str, Node],
        diff_attributes: HashableModelDiff | None,
        diff_relationships: HashableModelDiff | None,
        at: Timestamp,
        user_id: str,
    ) -> None:
        """Create, update, or delete attribute and relationship DB nodes based on the schema diff.

        Raises:
            ValueError: When an attribute or relationship marked for update or removal cannot be found in the existing items.

        """
        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        if diff_attributes:
            for item in node.local_attributes:
                # if item is in changed and has no ID, then it is being overridden from a generic and must be added
                if item.name in diff_attributes.added or (item.name in diff_attributes.changed and item.id is None):
                    created_item = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, db=db, parent=obj, at=at, user_id=user_id
                    )
                    new_attr = new_node.get_attribute(name=item.name)
                    new_attr.id = created_item.id
                elif item.name in diff_attributes.changed and item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], db=db, at=at, user_id=user_id)
                elif item.name in diff_attributes.removed and item.id and item.id in items:
                    await items[item.id].delete(db=db, user_id=user_id)
                elif (
                    (item.name in diff_attributes.removed or item.name in diff_attributes.changed)
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an attribute {item.name!r} to update or delete")

        if diff_relationships:
            for item in node.local_relationships:
                if self._is_virtual_relationship(item.name):
                    continue
                # if item is in changed and has no ID, then it is being overridden from a generic and must be added
                if item.name in diff_relationships.added or (
                    item.name in diff_relationships.changed and item.id is None
                ):
                    created_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, db=db, parent=obj, at=at, user_id=user_id
                    )
                    new_rel = new_node.get_relationship(name=item.name)
                    new_rel.id = created_rel.id
                elif item.name in diff_relationships.changed and item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], db=db, at=at, user_id=user_id)
                elif item.name in diff_relationships.removed and item.id and item.id in items:
                    await items[item.id].delete(db=db, user_id=user_id)
                elif (
                    (item.name in diff_relationships.removed or item.name in diff_relationships.changed)
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find a relationship {item.name!r} to update or delete")

        field_names_to_remove = []
        if diff_attributes and diff_attributes.removed:
            attr_names_to_remove = set(diff_attributes.removed.keys()) - set(node.local_attribute_names)
            field_names_to_remove.extend(list(attr_names_to_remove))
        if diff_relationships and diff_relationships.removed:
            rel_names_to_remove = set(diff_relationships.removed.keys()) - set(node.local_relationship_names)
            rel_names_to_remove -= self._virtual_relationship_names
            field_names_to_remove.extend(list(rel_names_to_remove))
        if field_names_to_remove:
            for field_schema in items.values():
                if field_schema.name.value in field_names_to_remove:
                    await field_schema.delete(db=db, at=at, user_id=user_id)

    async def delete_node_in_db(
        self,
        db: InfrahubDatabase,
        node: NodeSchema | GenericSchema,
        user_id: str,
        at: Timestamp,
        branch: Branch | str | None = None,
    ) -> None:
        """Delete the node with its attributes and relationships.

        Raises:
            SchemaNotFoundError: When no existing schema node matches the given node id on the branch.

        """
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db, prefetch_relationships=True)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        # First delete the attributes and the relationships
        for attr_schema_node in (await obj.attributes.get_peers(db=db)).values():
            await attr_schema_node.delete(db=db, at=at, user_id=user_id)
        for rel_schema_node in (await obj.relationships.get_peers(db=db)).values():
            await rel_schema_node.delete(db=db, at=at, user_id=user_id)

        await obj.delete(db=db, at=at, user_id=user_id)

    @staticmethod
    async def create_attribute_in_db(
        schema: NodeSchema,
        item: AttributeSchema,
        branch: Branch,
        parent: Node,
        db: InfrahubDatabase,
        user_id: str,
        at: Timestamp,
    ) -> AttributeSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.to_node(), node=parent, db=db)
        await obj.save(db=db, at=at, user_id=user_id)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_attribute_in_db(
        item: AttributeSchema, attr: Node, db: InfrahubDatabase, at: Timestamp, user_id: str
    ) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(attr, key).value = value
        await attr.save(db=db, at=at, user_id=user_id)

    @staticmethod
    async def create_relationship_in_db(
        schema: NodeSchema,
        item: RelationshipSchema,
        branch: Branch,
        parent: Node,
        db: InfrahubDatabase,
        user_id: str,
        at: Timestamp,
    ) -> RelationshipSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "state", "filters"}), node=parent, db=db)
        await obj.save(db=db, at=at, user_id=user_id)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_relationship_in_db(
        item: RelationshipSchema, rel: Node, db: InfrahubDatabase, at: Timestamp, user_id: str
    ) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(rel, key).value = value
        await rel.save(db=db, at=at, user_id=user_id)

    async def load_schema(
        self,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
    ) -> SchemaBranch:
        """Load the schema either from the cache or from the database."""
        branch = await registry.get_branch(branch=branch, db=db)

        if not branch.is_default and branch.origin_branch:
            origin_branch: Branch = await registry.get_branch(branch=branch.origin_branch, db=db)

            if origin_branch.active_schema_hash.main == branch.active_schema_hash.main:
                origin_schema = self.get_schema_branch(name=origin_branch.name)
                new_branch_schema = origin_schema.duplicate()
                self.set_schema_branch(name=branch.name, schema=new_branch_schema)
                log.info("Loading schema from cache")
                return new_branch_schema

        current_schema = self.get_schema_branch(name=branch.name)
        schema_diff = None
        if branch.active_schema_hash.is_valid and current_schema.get_hash_full().is_valid:
            schema_diff = current_schema.get_hash_full().compare(branch.active_schema_hash)
        branch_schema = await self.load_schema_from_db(
            db=db, branch=branch, schema=current_schema, schema_diff=schema_diff
        )
        self.set_schema_branch(name=branch.name, schema=branch_schema)
        return branch_schema

    async def load_schema_from_db(
        self,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
        schema: SchemaBranch | None = None,
        schema_diff: SchemaBranchDiff | None = None,
        at: Timestamp | None = None,
        validate_schema: bool = True,
    ) -> SchemaBranch:
        """Query all the node of type NodeSchema and GenericSchema from the database and convert them to their respective type.

        Args:
            db: Database Driver
            branch: Name of the branch to load the schema from. Defaults to None.
            schema: (Optional) If a schema is provided, it will be updated with the latest value, if not a new one will be created.
            schema_diff: (Optional). list of nodes, generics & groups to query

        Returns:
            SchemaBranch

        """
        branch = await registry.get_branch(branch=branch, db=db)
        schema = schema or SchemaBranch(cache=self._cache, name=branch.name)

        # If schema_diff has been provided, we need to build the proper filters for the queries based on the namespace and the name of the object.
        # the namespace and the name will be extracted from the kind with the function `parse_node_kind`
        filters = {"generics": {}, "nodes": {}}
        has_filters = False

        # If a diff is provided but is empty there is nothing to query
        if schema_diff is not None and not schema_diff.has_diff:
            return schema

        if schema_diff:
            log.info("Loading schema from DB", schema_to_update=schema_diff.to_list())

            for node_type in list(filters.keys()):
                filter_value = {
                    "namespace__values": list(
                        {parse_node_kind(item).namespace for item in getattr(schema_diff, node_type)}
                    ),
                    "name__values": list({parse_node_kind(item).name for item in getattr(schema_diff, node_type)}),
                }

                if filter_value["namespace__values"]:
                    filters[node_type] = filter_value
                    has_filters = True
            for removed_generic in schema_diff.removed_generics:
                if removed_generic in schema.generic_names:
                    schema.delete(name=removed_generic)
            for removed_node in schema_diff.removed_nodes:
                if removed_node in schema.node_names:
                    schema.delete(name=removed_node)

        if not has_filters or filters["generics"]:
            generic_schema = self.get(name="SchemaGeneric", branch=branch)
            for schema_node in await self.query(
                schema=generic_schema,
                branch=branch,
                at=at,
                filters=filters["generics"],
                prefetch_relationships=True,
                db=db,
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_generic_schema_to_schema(schema_node=schema_node, db=db),
                )

        if not has_filters or filters["nodes"]:
            node_schema = self.get(name="SchemaNode", branch=branch)
            for schema_node in await self.query(
                schema=node_schema, branch=branch, at=at, filters=filters["nodes"], prefetch_relationships=True, db=db
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_node_schema_to_schema(schema_node=schema_node, db=db),
                )

        schema.process(validate_schema=validate_schema)

        return schema

    @classmethod
    async def _prepare_node_data(cls, schema_node: Node, db: InfrahubDatabase) -> dict[str, Any]:
        node_data = {"id": schema_node.id}

        # First pull all the local attributes at the top level, then convert all the local relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            attr = getattr(schema_node, attr_name)
            node_data[attr_name] = attr.get_value()

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                if cls._is_virtual_relationship(rel_name):
                    continue
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(db=db):
                item = await rel.get_peer(db=db)
                item_data = {"id": item.id}
                inherited_attr = getattr(item, "inherited", None)
                if inherited_attr and getattr(inherited_attr, "value", False) is True:
                    continue
                for item_name in item._attributes:
                    item_attr = getattr(item, item_name)
                    item_data[item_name] = item_attr.get_value()

                node_data[rel_name].append(item_data)
        return node_data

    @classmethod
    async def convert_node_schema_to_schema(cls, schema_node: Node, db: InfrahubDatabase) -> NodeSchema:
        """Convert a schema_node object loaded from the database into NodeSchema object."""
        node_data = await cls._prepare_node_data(schema_node=schema_node, db=db)
        return NodeSchema(**node_data)

    @classmethod
    async def convert_generic_schema_to_schema(cls, schema_node: Node, db: InfrahubDatabase) -> GenericSchema:
        """Convert a schema_node object loaded from the database into GenericSchema object."""
        node_data = await cls._prepare_node_data(schema_node=schema_node, db=db)
        return GenericSchema(**node_data)

    def purge_inactive_branches(self, active_branches: list[str]) -> list[str]:
        """Return non active branches that were purged."""
        hashes_to_keep: set[str] = set()
        branch_processed: set[str] = set()
        for active_branch in active_branches:
            branch_hash = self._branch_hash_by_name.get(active_branch)
            if not branch_hash or branch_hash not in branch_processed:
                if branch_hash:
                    branch_processed.add(branch_hash)
                if branch := self._branches.get(active_branch):
                    nodes = branch.get_all(include_internal=True, duplicate=False)
                    hashes_to_keep.update([node.get_hash() for node in nodes.values()])

        removed_branches: list[str] = []
        for branch_name in list(self._branches.keys()):
            if branch_name not in active_branches:
                del self._branches[branch_name]
                if branch_name in self._branch_hash_by_name:
                    del self._branch_hash_by_name[branch_name]
                removed_branches.append(branch_name)

        for hash_key in list(self._cache.keys()):
            if hash_key not in hashes_to_keep:
                del self._cache[hash_key]

        return removed_branches

    def get_branches(self) -> list[str]:
        return list(self._branches.keys())
