from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import lock
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
from infrahub.core.utils import parse_node_kind
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

from .constants import IGNORE_FOR_NODE
from .schema_branch import SchemaBranch

log = get_logger()

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class SchemaManager(NodeManager):
    def __init__(self) -> None:
        self._cache: dict[int, Any] = {}
        self._branches: dict[str, SchemaBranch] = {}

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

    async def get_full_safe(self, branch: Branch | str | None = None) -> dict[str, NodeSchema | GenericSchema]:
        await lock.registry.local_schema_wait()

        return self.get_full(branch=branch)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name in self._branches:
            return self._branches[name]

        self._branches[name] = SchemaBranch(cache=self._cache, name=name)
        return self._branches[name]

    def set_schema_branch(self, name: str, schema: SchemaBranch) -> None:
        schema.name = name
        self._branches[name] = schema

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
    ) -> None:
        branch = await registry.get_branch(branch=branch, db=db)

        updated_schema = None
        if update_db:
            if diff:
                schema_diff = await self.update_schema_to_db(schema=schema, db=db, branch=branch, diff=diff)
            else:
                await self.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit)
                # After updating the schema into the db
                # we need to pull a fresh version because some default value are managed/generated within the node object
                schema_diff = None
                if limit:
                    schema_diff = SchemaBranchDiff(
                        added_nodes=[name for name in list(schema.nodes.keys()) if name in limit],
                        added_generics=[name for name in list(schema.generics.keys()) if name in limit],
                    )

            updated_schema = await self.load_schema_from_db(
                db=db, branch=branch, schema=schema, schema_diff=schema_diff
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
        branch: Branch | str | None = None,
    ) -> SchemaBranchDiff:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        added_nodes = []
        added_generics = []
        for item_kind in diff.added.keys():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.load_node_to_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            if item.is_node_schema:
                added_nodes.append(item_kind)
            else:
                added_generics.append(item_kind)

        changed_nodes = []
        changed_generics = []
        for item_kind, item_diff in diff.changed.items():
            item = schema.get(name=item_kind, duplicate=False)
            if item_diff:
                node = await self.update_node_in_db_based_on_diff(node=item, branch=branch, db=db, diff=item_diff)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            if item.is_node_schema:
                changed_nodes.append(item_kind)
            else:
                changed_generics.append(item_kind)

        removed_nodes = []
        removed_generics = []
        for item_kind in diff.removed.keys():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.delete_node_in_db(node=item, branch=branch, db=db)
            schema.delete(name=item_kind)
            if item.is_node_schema:
                removed_nodes.append(item_kind)
            else:
                removed_generics.append(item_kind)

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
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        for item_kind in schema.node_names + schema.generic_names_without_templates:
            if limit and item_kind not in limit:
                continue
            item = schema.get(name=item_kind, duplicate=False)
            if not item.id:
                node = await self.load_node_to_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)

    async def load_node_to_db(
        self,
        node: NodeSchema | GenericSchema,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
    ) -> NodeSchema | GenericSchema:
        """Load a Node with its attributes and its relationships to the database."""
        branch = await registry.get_branch(branch=branch, db=db)

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
        await obj.save(db=db)
        new_node.id = obj.id

        # Then create the Attributes and the relationships
        if isinstance(node, NodeSchema | GenericSchema):
            new_node.relationships = []
            new_node.attributes = []

            for item in node.attributes:
                if item.inherited is False:
                    new_attr = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, parent=obj, branch=branch, db=db
                    )
                else:
                    new_attr = item.duplicate()
                new_node.attributes.append(new_attr)

            for item in node.relationships:
                if item.inherited is False:
                    new_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, parent=obj, branch=branch, db=db
                    )
                else:
                    new_rel = item.duplicate()
                new_node.relationships.append(new_rel)

        # Save back the node with the newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db(
        self,
        db: InfrahubDatabase,
        node: NodeSchema | GenericSchema,
        branch: Branch | str | None = None,
    ) -> NodeSchema | GenericSchema:
        """Update a Node with its attributes and its relationships in the database."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        schema_dict = node.model_dump(exclude=IGNORE_FOR_NODE)
        for key, value in schema_dict.items():
            getattr(obj, key).value = value

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        new_node = node.duplicate()

        # Update the attributes and the relationships nodes as well
        await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])
        await obj.relationships.update(
            db=db, data=[item.id for item in node.local_relationships if item.id and item.name != "profiles"]
        )
        await obj.save(db=db)

        # Then Update the Attributes and the relationships

        items = await self.get_many(
            ids=[item.id for item in node.local_attributes + node.local_relationships if item.id],
            db=db,
            branch=branch,
            include_owner=True,
            include_source=True,
        )

        for item in node.local_attributes:
            if item.id and item.id in items:
                await self.update_attribute_in_db(item=item, attr=items[item.id], db=db)
            elif not item.id:
                new_attr = await self.create_attribute_in_db(
                    schema=attribute_schema, item=item, branch=branch, db=db, parent=obj
                )
                new_node.attributes.append(new_attr)

        for item in node.local_relationships:
            if item.id and item.id in items:
                await self.update_relationship_in_db(item=item, rel=items[item.id], db=db)
            elif not item.id:
                new_rel = await self.create_relationship_in_db(
                    schema=relationship_schema, item=item, branch=branch, db=db, parent=obj
                )
                new_node.relationships.append(new_rel)

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db_based_on_diff(
        self,
        db: InfrahubDatabase,
        diff: HashableModelDiff,
        node: NodeSchema | GenericSchema,
        branch: Branch | str | None = None,
    ) -> NodeSchema | GenericSchema:
        """Update a Node with its attributes and its relationships in the database based on a HashableModelDiff."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        properties_to_update = set(list(diff.added.keys()) + list(diff.changed.keys())) - IGNORE_FOR_NODE

        if properties_to_update:
            schema_dict = node.model_dump(exclude=IGNORE_FOR_NODE)
            for key, value in schema_dict.items():
                getattr(obj, key).value = value

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        new_node = node.duplicate()

        diff_attributes = diff.changed.get("attributes")
        diff_relationships = diff.changed.get("relationships")
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

        items: dict[str, Node] = {}
        if item_ids:
            items = await self.get_many(
                ids=list(item_ids),
                db=db,
                branch=branch,
                include_owner=True,
                include_source=True,
            )
        if missing_field_names:
            missing_attrs = await self.query(
                db=db,
                branch=branch,
                schema=attribute_schema,
                filters={"name__values": missing_field_names, "node__id": node.id},
                include_owner=True,
                include_source=True,
            )
            missing_rels = await self.query(
                db=db,
                branch=branch,
                schema=relationship_schema,
                filters={"name__values": missing_field_names, "node__id": node.id},
                include_owner=True,
                include_source=True,
            )
            items.update({field.id: field for field in missing_attrs + missing_rels})

        if diff_attributes:
            await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])

        if diff_relationships:
            await obj.relationships.update(db=db, data=[item.id for item in node.local_relationships if item.id])

        await obj.save(db=db)

        if diff_attributes:
            for item in node.local_attributes:
                # if item is in changed and has no ID, then it is being overridden from a generic and must be added
                if item.name in diff_attributes.added or item.name in diff_attributes.changed and item.id is None:
                    created_item = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_attr = new_node.get_attribute(name=item.name)
                    new_attr.id = created_item.id
                elif item.name in diff_attributes.changed and item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], db=db)
                elif item.name in diff_attributes.removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
                elif (
                    (item.name in diff_attributes.removed or item.name in diff_attributes.changed)
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an attribute {item.name!r} to update or delete")

        if diff_relationships:
            for item in node.local_relationships:
                # if item is in changed and has no ID, then it is being overridden from a generic and must be added
                if item.name in diff_relationships.added or item.name in diff_relationships.changed and item.id is None:
                    created_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_rel = new_node.get_relationship(name=item.name)
                    new_rel.id = created_rel.id
                elif item.name in diff_relationships.changed and item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], db=db)
                elif item.name in diff_relationships.removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
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
            field_names_to_remove.extend(list(rel_names_to_remove))
        if field_names_to_remove:
            for field_schema in items.values():
                if field_schema.name.value in field_names_to_remove:
                    await field_schema.delete(db=db)

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def delete_node_in_db(
        self,
        db: InfrahubDatabase,
        node: NodeSchema | GenericSchema,
        branch: Branch | str | None = None,
    ) -> None:
        """Delete the node with its attributes and relationships."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        # First delete the attributes and the relationships
        items = await self.get_many(
            ids=[item.id for item in node.local_attributes + node.local_relationships if item.id],
            db=db,
            branch=branch,
            include_owner=True,
            include_source=True,
        )

        for item in items.values():
            await item.delete(db=db)

        await obj.delete(db=db)

    @staticmethod
    async def create_attribute_in_db(
        schema: NodeSchema, item: AttributeSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> AttributeSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.to_node(), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_attribute_in_db(item: AttributeSchema, attr: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(attr, key).value = value
        await attr.save(db=db)

    @staticmethod
    async def create_relationship_in_db(
        schema: NodeSchema, item: RelationshipSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> RelationshipSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "state", "filters"}), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_relationship_in_db(item: RelationshipSchema, rel: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(rel, key).value = value
        await rel.save(db=db)

    async def load_schema(
        self,
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
    ) -> SchemaBranch:
        """Load the schema either from the cache or from the database"""
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
                if rel_name == "profiles":
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
        for active_branch in active_branches:
            if branch := self._branches.get(active_branch):
                nodes = branch.get_all(include_internal=True, duplicate=False)
                hashes_to_keep.update([node.get_hash() for node in nodes.values()])

        removed_branches: list[str] = []
        for branch_name in list(self._branches.keys()):
            if branch_name not in active_branches:
                del self._branches[branch_name]
                removed_branches.append(branch_name)

        for hash_key in list(self._cache.keys()):
            if hash_key not in hashes_to_keep:
                del self._cache[hash_key]

        return removed_branches
