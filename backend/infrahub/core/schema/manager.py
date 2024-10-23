from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub import lock
from infrahub.core.constants import (
    InfrahubKind,
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


# pylint: disable=too-many-public-methods
class SchemaManager(NodeManager):
    def __init__(self) -> None:
        self._cache: dict[int, Any] = {}
        self._branches: dict[str, SchemaBranch] = {}

    def _get_from_cache(self, key: int) -> Any:
        return self._cache[key]

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema], branch: Optional[str] = None) -> int:
        branch = branch or registry.default_branch

        if branch not in self._branches:
            self._branches[branch] = SchemaBranch(cache=self._cache, name=branch)

        self._branches[branch].set(name=name, schema=schema)

        return hash(self._branches[branch])

    def has(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        try:
            self.get(name=name, branch=branch, duplicate=False)
            return True
        except SchemaNotFoundError:
            return False

    def get(
        self,
        name: str,
        branch: Optional[Union[Branch, str]] = None,
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

    def get_node_schema(
        self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> NodeSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, NodeSchema):
            return schema

        raise ValueError("The selected node is not of type NodeSchema")

    def get_profile_schema(
        self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> ProfileSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, ProfileSchema):
            return schema

        raise ValueError("The selected node is not of type ProfileSchema")

    def get_full(
        self, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> dict[str, MainSchemaTypes]:
        branch = registry.get_branch_from_registry(branch=branch)

        branch_name = None
        if branch.name in self._branches:
            branch_name = branch.name
        else:
            branch_name = registry.default_branch

        return self._branches[branch_name].get_all(duplicate=duplicate)

    async def get_full_safe(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> dict[str, Union[NodeSchema, GenericSchema]]:
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
        branch: Optional[Union[Branch, str]] = None,
        diff: Optional[SchemaDiff] = None,
        limit: Optional[list[str]] = None,
        update_db: bool = True,
    ) -> None:
        branch = await registry.get_branch(branch=branch, db=db)

        updated_schema = None
        if update_db:
            schema_diff = None
            if diff:
                schema_diff = await self.update_schema_to_db(schema=schema, db=db, branch=branch, diff=diff)
            else:
                await self.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit)
                # After updating the schema into the db
                # we need to pull a fresh version because some default value are managed/generated within the node object
                schema_diff = None
                if limit:
                    schema_diff = SchemaBranchDiff(
                        nodes=[name for name in list(schema.nodes.keys()) if name in limit],
                        generics=[name for name in list(schema.generics.keys()) if name in limit],
                    )

            updated_schema = await self.load_schema_from_db(
                db=db, branch=branch, schema=schema, schema_diff=schema_diff
            )

        self.set_schema_branch(name=branch.name, schema=updated_schema or schema)

    def register_schema(self, schema: SchemaRoot, branch: Optional[str] = None) -> SchemaBranch:
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
        branch: Optional[Union[str, Branch]] = None,
    ) -> SchemaBranchDiff:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        item_kinds = []
        for item_kind, item_diff in diff.added.items():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.load_node_to_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            item_kinds.append(item_kind)

        for item_kind, item_diff in diff.changed.items():
            item = schema.get(name=item_kind, duplicate=False)
            if item_diff:
                node = await self.update_node_in_db_based_on_diff(node=item, branch=branch, db=db, diff=item_diff)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            item_kinds.append(item_kind)

        for item_kind, item_diff in diff.removed.items():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.delete_node_in_db(node=item, branch=branch, db=db)
            schema.delete(name=item_kind)

        schema_diff = SchemaBranchDiff(
            nodes=[name for name in schema.node_names if name in item_kinds],
            generics=[name for name in schema.generic_names if name in item_kinds],
        )
        return schema_diff

    async def load_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
        limit: Optional[list[str]] = None,
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        for item_kind in schema.node_names + schema.generic_names:
            if item_kind == InfrahubKind.PROFILE:
                continue
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
        node: Union[NodeSchema, GenericSchema],
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
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
        if isinstance(node, (NodeSchema, GenericSchema)):
            new_node.relationships = []
            new_node.attributes = []

            for item in node.attributes:
                new_attr = await self.create_attribute_in_db(
                    schema=attribute_schema, item=item, parent=obj, branch=branch, db=db
                )
                new_node.attributes.append(new_attr)

            for item in node.relationships:
                new_rel = await self.create_relationship_in_db(
                    schema=relationship_schema, item=item, parent=obj, branch=branch, db=db
                )
                new_node.relationships.append(new_rel)

        # Save back the node with the newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db(
        self,
        db: InfrahubDatabase,
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
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

    async def update_node_in_db_based_on_diff(  # pylint: disable=too-many-branches,too-many-statements
        self,
        db: InfrahubDatabase,
        diff: HashableModelDiff,
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
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

        # Update the attributes and the relationships nodes as well
        if "attributes" in diff.changed:
            await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])

        if "relationships" in diff.changed:
            await obj.relationships.update(db=db, data=[item.id for item in node.local_relationships if item.id])

        await obj.save(db=db)

        # Then Update the Attributes and the relationships
        def get_attrs_rels_to_update(diff: HashableModelDiff) -> list[str]:
            items_to_update = []
            if "attributes" in diff.changed.keys() and diff.changed["attributes"]:
                items_to_update.extend(list(diff.changed["attributes"].added.keys()))
                items_to_update.extend(list(diff.changed["attributes"].changed.keys()))
                items_to_update.extend(list(diff.changed["attributes"].removed.keys()))
            if "relationships" in diff.changed.keys() and diff.changed["relationships"]:
                items_to_update.extend(list(diff.changed["relationships"].added.keys()))
                items_to_update.extend(list(diff.changed["relationships"].changed.keys()))
                items_to_update.extend(list(diff.changed["relationships"].removed.keys()))
            return items_to_update

        attrs_rels_to_update = get_attrs_rels_to_update(diff=diff)

        items = await self.get_many(
            ids=[
                item.id
                for item in node.local_attributes + node.local_relationships
                if item.id and item.name in attrs_rels_to_update
            ],
            db=db,
            branch=branch,
            include_owner=True,
            include_source=True,
        )

        if "attributes" in diff.changed.keys() and diff.changed["attributes"]:
            for item in node.local_attributes:
                if item.name in diff.changed["attributes"].added:
                    created_item = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_attr = new_node.get_attribute(name=item.name)
                    new_attr.id = created_item.id
                elif item.name in diff.changed["attributes"].changed and item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], db=db)
                elif item.name in diff.changed["attributes"].removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
                elif (
                    (item.name in diff.changed["attributes"].removed or item.name in diff.changed["attributes"].changed)
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an attribute {item.name!r} to update or delete")

        if "relationships" in diff.changed.keys() and diff.changed["relationships"]:
            for item in node.local_relationships:
                if item.name in diff.changed["relationships"].added:
                    created_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_rel = new_node.get_relationship(name=item.name)
                    new_rel.id = created_rel.id
                elif item.name in diff.changed["relationships"].changed and item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], db=db)
                elif item.name in diff.changed["relationships"].removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
                elif (
                    (
                        item.name in diff.changed["relationships"].removed
                        or item.name in diff.changed["relationships"].changed
                    )
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an relationship {item.name!r} to update or delete")

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def delete_node_in_db(
        self,
        db: InfrahubDatabase,
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
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
        await obj.new(**item.model_dump(exclude={"id", "state", "filters"}), node=parent, db=db)
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
        branch: Optional[Union[str, Branch]] = None,
    ) -> SchemaBranch:
        """Load the schema either from the cache or from the database"""
        branch = await registry.get_branch(branch=branch, db=db)

        if not branch.is_default and branch.origin_branch:
            origin_branch: Branch = await registry.get_branch(branch=branch.origin_branch, db=db)

            if origin_branch.schema_hash.main == branch.schema_hash.main:
                origin_schema = self.get_schema_branch(name=origin_branch.name)
                new_branch_schema = origin_schema.duplicate()
                self.set_schema_branch(name=branch.name, schema=new_branch_schema)
                log.info("Loading schema from cache")
                return new_branch_schema

        current_schema = self.get_schema_branch(name=branch.name)
        schema_diff = current_schema.get_hash_full().compare(branch.schema_hash)
        branch_schema = await self.load_schema_from_db(
            db=db, branch=branch, schema=current_schema, schema_diff=schema_diff
        )
        self.set_schema_branch(name=branch.name, schema=branch_schema)
        return branch_schema

    async def load_schema_from_db(
        self,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
        schema: Optional[SchemaBranch] = None,
        schema_diff: Optional[SchemaBranchDiff] = None,
        at: Optional[Timestamp] = None,
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
        if schema_diff is not None and not schema_diff:
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
