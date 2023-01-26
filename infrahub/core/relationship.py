from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypeVar, Union
from uuid import UUID

from infrahub.core import registry
from infrahub.core.property import FlagPropertyMixin, NodePropertyMixin
from infrahub.core.query.relationship import (
    RelationshipCreateQuery,
    RelationshipDataDeleteQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipGetQuery,
    RelationshipPeerData,
    RelationshipUpdatePropertyQuery,
)
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to
from infrahub.exceptions import ValidationError
from infrahub.utils import intersection

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema, RelationshipSchema

# RELATIONSHIPS_MAPPING = {"Relationship": Relationship}

SelfRelationship = TypeVar("SelfRelationship", bound="Relationship")
SelfRelationshipManager = TypeVar("SelfRelationshipManager", bound="RelationshipManager")


class Relationship(FlagPropertyMixin, NodePropertyMixin):

    rel_type: str = "IS_RELATED"

    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Optional[Timestamp] = None,
        node: Optional[Node] = None,
        node_id: Optional[str] = None,
        *args,
        **kwargs,
    ):

        if not node and not node_id:
            raise ValueError("Either node or node_id must be provided.")

        self.schema = schema
        self.name = schema.name

        self.branch = branch
        self.at = Timestamp(at)

        self._node = node
        self.node_id = node_id or node.id

        self.id = None
        self.db_id = None
        self.updated_at = None

        self._peer = None
        self.peer_id = None

        self._init_node_property_mixin(kwargs=kwargs)
        self._init_flag_property_mixin(kwargs=kwargs)

    async def _process_data(self, session: AsyncSession, data: Union[Dict, RelationshipPeerData, str]):

        self.data = data

        prop_prefix = "_relation__"

        if isinstance(data, RelationshipPeerData):
            await self.set_peer(data.peer_id)

            if not self.id and data.rel_node_id:
                self.id = data.rel_node_id
            if not self.db_id and data.rel_node_db_id:
                self.db_id = data.rel_node_db_id

            # Extract the properties
            for prop_name, prop in data.properties.items():
                if hasattr(self, "_flag_properties") and prop_name in self._flag_properties:
                    setattr(self, prop_name, prop.value)
                elif hasattr(self, "_node_properties") and prop_name in self._node_properties:
                    setattr(self, prop_name, prop.value)

        elif isinstance(data, dict):
            for key, value in data.items():
                if key in ["peer", "id"]:
                    await self.set_peer(value=data.get(key, None))
                elif key.startswith(prop_prefix) and hasattr(self, key.replace(prop_prefix, "")):
                    setattr(self, key.replace(prop_prefix, ""), value)

        else:
            await self.set_peer(value=data)

    async def new(
        self,
        session: AsyncSession,
        data: Union[dict, RelationshipPeerData, Any] = None,
        *args,
        **kwargs,
    ) -> SelfRelationship:

        await self._process_data(session=session, data=data)

        return self

    async def load(
        self,
        session: AsyncSession,
        id: str = None,
        db_id: int = None,
        updated_at: Union[Timestamp, str] = None,
        data: Union[dict, RelationshipPeerData, Any] = None,
    ) -> SelfRelationship:

        self.id = id
        self.db_id = db_id

        if updated_at:
            self.updated_at = Timestamp(updated_at)

        await self._process_data(session=session, data=data)

        return self

    def get_kind(self) -> str:
        """Return the kind of the relationship."""
        return self.schema.kind

    async def get_node(self, session: AsyncSession):
        """Return the node of the relationship."""
        if self._node is None:
            await self._get_node(session=session)

        return self._node

    async def _get_node(self, session: AsyncSession) -> bool:
        from infrahub.core.manager import NodeManager

        self._node = await NodeManager.get_one(session=session, id=self.node_id, branch=self.branch, at=self.at)

        if self._node:
            return True

        if not self.schema.default_filter:
            return False

        # if a default_filter is defined, try to query the node by its default filter
        results = await NodeManager.query(
            session=session,
            schema=self.schema,
            filters={self.schema.default_filterr: self.node_id},
            branch=self.branch,
            at=self.at,
        )

        if not results:
            return False

        self._node = results[0]
        self.node_id = self._node.id

        return True

    async def set_peer(self, value: Union[Node, str]):
        if hasattr(value, "_schema"):
            if value.get_kind() != self.schema.peer and self.schema.peer not in value._schema.inherit_from:

                peer_schema = registry.get_schema(name=value.get_kind(), branch=self.branch)

                if self.schema.peer not in peer_schema.groups:
                    raise ValidationError(
                        {self.name: f"Got an object of type {value.get_kind()} instead of {self.schema.peer}"}
                    )

            self._peer = value
            self.peer_id = value.id
            return True

        if isinstance(value, str):
            self.peer_id = value
            return True

        raise ValidationError({self.name: f"Unsupported type ({type(value)}) must be a string or a node object"})

    async def get_peer(self, session: AsyncSession):
        """Return the peer of the relationship."""
        if self._peer is None:
            await self._get_peer(session=session)

        return self._peer if self._peer else None

    async def _get_peer(self, session: AsyncSession):
        from infrahub.core.manager import NodeManager

        self._peer = await NodeManager.get_one(session=session, id=self.peer_id, branch=self.branch, at=self.at)

        peer_schema = await self.get_peer_schema(session=session)
        results = None
        if not self._peer and peer_schema.default_filter:
            results = await NodeManager.query(
                session=session,
                schema=peer_schema,
                filters={peer_schema.default_filter: self.peer_id},
                branch=self.branch,
                at=self.at,
            )

        if not results:
            return None

        self._peer = results[0]
        self.peer_id = self._peer.id

    async def get_peer_schema(self, session: AsyncSession) -> NodeSchema:
        return registry.get_schema(name=self.schema.peer, branch=self.branch)

    def compare_properties_with_data(self, data: RelationshipPeerData) -> List[str]:

        different_properties = []

        for prop_name, prop in data.properties.items():
            if hasattr(self, "_flag_properties") and prop_name in self._flag_properties:
                if prop.value != getattr(self, prop_name):
                    different_properties.append(prop_name)

            elif hasattr(self, "_node_properties") and prop_name in self._node_properties:
                if prop.value != getattr(self, f"{prop_name}_id"):
                    different_properties.append(prop_name)

        return different_properties

    async def _create(self, session: AsyncSession, at: Optional[Timestamp] = None):
        """Add a relationship with another object by creating a new relationship node."""

        create_at = Timestamp(at)

        # Assuming nothing is present in the database yet
        # Create a new Relationship node and attach each object to it
        node = await self.get_node(session=session)
        peer = await self.get_peer(session=session)
        query = await RelationshipCreateQuery.init(
            session=session, source=node, destination=peer, rel=self, branch=self.branch, at=create_at
        )
        await query.execute(session=session)
        result = query.get_result()

        self.db_id = result.get("rl").element_id
        self.id = result.get("rl").get("uuid")

    async def update(
        self,
        session: AsyncSession,
        properties_to_update: List[str],
        data: RelationshipPeerData,
        at: Optional[Timestamp] = None,
    ):
        """Update the properties of an existing relationship."""

        update_at = Timestamp(at)

        rel_ids_to_update = []
        for prop_name, prop in data.properties.items():
            if prop_name in properties_to_update and prop.rel.branch == self.branch.name:
                rel_ids_to_update.append(prop.rel.db_id)

        if rel_ids_to_update:
            await update_relationships_to(rel_ids_to_update, to=update_at, session=session)

        node = await self.get_node(session=session)

        query = await RelationshipUpdatePropertyQuery.init(
            session=session,
            source=node,
            rel=self,
            properties_to_update=properties_to_update,
            data=data,
            branch=self.branch,
            at=update_at,
        )
        await query.execute(session=session)

    async def delete(self, session: AsyncSession, at: Optional[Timestamp] = None):

        delete_at = Timestamp(at)

        node = await self.get_node(session=session)
        peer = await self.get_peer(session=session)

        query = await RelationshipGetQuery.init(
            session=session, source=node, destination=peer, rel=self, branch=self.branch, at=delete_at
        )
        await query.execute(session=session)
        result = query.get_result()

        # when we remove a relationship we need to :
        # - Update the existing relationship if we are on the same branch
        # - Create a new rel of type DELETED in the right branch

        if rel_ids_to_update := [rel.element_id for rel in result.get_rels() if rel.get("branch") == self.branch.name]:
            await update_relationships_to(rel_ids_to_update, to=delete_at, session=session)

        query = await RelationshipDeleteQuery.init(
            session=session, rel=self, source=node, destination=peer, branch=self.branch, at=delete_at
        )
        await query.execute(session=session)

    async def save(self, at: Optional[Timestamp] = None, session: Optional[AsyncSession] = None) -> SelfRelationship:
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)

        if not self.id:
            await self._create(at=save_at, session=session)
            return self

        return self

    async def to_graphql(self, fields: dict, session: AsyncSession) -> dict:
        """Generate GraphQL Payload for the associated Peer."""

        peer_fields = {key: value for key, value in fields.items() if not key.startswith("_relation")}

        peer = await self.get_peer(session=session)
        response = await peer.to_graphql(fields=peer_fields, session=session)

        if "_relation__updated_at" in fields:
            response["_relation__updated_at"] = await self.updated_at.to_graphql(session=session)

        return response


class RelationshipManager:
    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        # data: Optional[Union[Dict, List, str]] = None,
        *args,
        **kwargs,
    ):

        self.schema: RelationshipSchema = schema
        self.name: str = schema.name
        self.node: Node = node
        self.branch: Branch = branch
        self.at = at

        # TODO Ideally this information should come from the Schema
        self.rel_class = Relationship

        self._relationships: List[Relationship] = []
        self.has_fetched_relationships: bool = False

    @classmethod
    async def init(
        cls,
        session: AsyncSession,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        data: Optional[Union[Dict, List, str]] = None,
        *args,
        **kwargs,
    ):

        rm = cls(schema=schema, branch=branch, at=at, node=node, *args, **kwargs)

        # By default we are not loading the relationships
        # These will be accessed on demand, if needed
        if data is None:
            return rm

        # Data can be
        #  - A String, pass it to one relationsip object
        #  - A Dict, pass it to one relationship object
        #  - A list of str or dict, pass it to multiple objects
        if not isinstance(data, list):
            data = [data]

        for item in data:

            if not isinstance(item, (rm.rel_class, str, dict)) and not hasattr(item, "_schema"):
                raise ValidationError({rm.name: f"Invalid data provided to form a relationship {item}"})

            rel = rm.rel_class(schema=rm.schema, branch=rm.branch, at=rm.at, node=rm.node)
            await rel.new(session=session, data=item)

            rm._relationships.append(rel)

        rm.has_fetched_relationships = True

        return rm

    def get_kind(self) -> str:
        return self.schema.kind

    def __iter__(self):
        if self.schema.cardinality == "one":
            raise TypeError("relationship with single cardinality are not iterable")

        if not self.has_fetched_relationships:
            raise LookupError("you can't iterate over the relationships before the cache has been populated.")

        return iter(self._relationships)

    async def get_peer(self, session: AsyncSession) -> Optional[Node]:
        if self.schema.cardinality == "many":
            raise TypeError("peer is not available for relationship with multiple cardinality")

        rels = await self.get_relationships(session=session)
        if not rels:
            return None

        return await rels[0].get_peer(session=session)

    async def _fetch_relationship_ids(
        self, at: Optional[Timestamp] = None, session: Optional[AsyncSession] = None
    ) -> Tuple[List[str], List[str], List[str], Dict[str, RelationshipPeerData]]:
        """Fetch the latest relationships from the database and returns :
        - the list of nodes present on both sides
        - the list of nodes present only locally
        - the list of nodes present only in the database
        """

        current_peer_ids = [rel.peer_id for rel in self._relationships]

        query = await RelationshipGetPeerQuery.init(
            session=session,
            source=self.node,
            at=at or self.at,
            rel=self.rel_class(schema=self.schema, branch=self.branch, node=self.node),
        )
        await query.execute(session=session)

        peers_database: dict = {peer.peer_id: peer for peer in query.get_peers()}
        peer_ids = list(peers_database.keys())

        # Calculate which peer should be added or removed
        peer_ids_present_both = intersection(current_peer_ids, peer_ids)
        peer_ids_present_local_only = list(set(current_peer_ids) - set(peer_ids_present_both))
        peer_ids_present_database_only = list(set(peer_ids) - set(peer_ids_present_both))

        return peer_ids_present_both, peer_ids_present_local_only, peer_ids_present_database_only, peers_database

    async def _fetch_relationships(self, session: AsyncSession, at: Optional[Timestamp] = None):
        """Fetch the latest relationships from the database and update the local cache."""

        (
            _,
            peer_ids_present_local_only,
            peer_ids_present_database_only,
            peers_database,
        ) = await self._fetch_relationship_ids(at=at, session=session)

        for peer_id in peer_ids_present_database_only:
            self._relationships.append(
                await Relationship(
                    schema=self.schema,
                    branch=self.branch,
                    at=at or self.at,
                    node=self.node,
                ).load(session=session, data=peers_database[peer_id])
            )

        self.has_fetched_relationships = True

        for peer_id in peer_ids_present_local_only:
            await self.remove(peer_id=peer_id, session=session)

    async def get(self, session: AsyncSession) -> Union[Relationship, List[Relationship]]:

        rels = await self.get_relationships(session=session)

        if self.schema.cardinality == "one":
            return rels[0]

        return rels

    async def get_relationships(self, session: AsyncSession) -> List[Relationship]:

        if not self.has_fetched_relationships:
            await self._fetch_relationships(session=session)

        return self._relationships

    async def update(self, data: Union[List[str], List[Node], str, Node], session: AsyncSession) -> bool:
        """Replace and Update the list of relationships with this one."""
        if not isinstance(data, list):
            data = [data]

        # Reset the list of relationship and save the previous one to see if we can reuse some
        previous_relationships = {rel.peer_id: rel for rel in await self.get_relationships(session=session)}
        self._relationships = []

        changed = False
        for item in data:
            if not isinstance(item, (self.rel_class, str, dict)) and not hasattr(item, "_schema"):
                raise ValidationError({self.name: f"Invalid data provided to form a relationship {item}"})

            if hasattr(item, "_schema") and item.id in previous_relationships:
                self._relationships.append(previous_relationships[item.id])
                continue

            if isinstance(item, str) and item in previous_relationships:
                self._relationships.append(previous_relationships[item])
                continue

            if isinstance(item, dict) and item.get("id", None) in previous_relationships:
                rel = previous_relationships[item["id"]]
                await rel.load(data=item, session=session)
                # TODO Add a check to identify if the relationship was changed or not
                # changed = True
                self._relationships.append(rel)
                continue

            # If the item is not present in the previous list of relationship, we create a new one.
            self._relationships.append(
                await self.rel_class(schema=self.schema, branch=self.branch, at=self.at, node=self.node).new(
                    session=session, data=item
                )
            )
            changed = True

        # Check if some relationship got removed by checking if the previous list of relationship is a subset of the current list of not
        if set(list(previous_relationships.keys())) <= {
            rel.peer_id for rel in await self.get_relationships(session=session)
        }:
            changed = True

        return changed

    async def remove(
        self,
        peer_id: UUID,
        session: AsyncSession,
        update_db: bool = False,
    ):
        """Remote a peer id from the local relationships list,
        need to investigate if and when we should update the relationship in the database."""

        for idx, rel in enumerate(await self.get_relationships(session=session)):
            if rel.peer_id != peer_id:
                continue

            if update_db:
                await rel.delete(session=session)

            self._relationships.pop(idx)
            return True

        raise Exception("Relationship not found ... unexpected")

    async def remove_in_db(
        self,
        peer_id: UUID,
        peer_data: RelationshipPeerData,
        at: Optional[Timestamp] = None,
        session: Optional[AsyncSession] = None,
    ):

        remove_at = Timestamp(at)

        # when we remove a relationship we need to :
        # - Update the existing relationship if we are on the same branch
        # - Create a new rel of type DELETED in the right branch
        rel_ids_per_branch = peer_data.rel_ids_per_branch()
        if self.branch.name in rel_ids_per_branch:
            await update_relationships_to(rel_ids_per_branch[self.branch.name], to=remove_at, session=session)

        query = await RelationshipDataDeleteQuery.init(
            session=session,
            rel=self.rel_class,
            schema=self.schema,
            source=self.node,
            data=peer_data,
            branch=self.branch,
            at=remove_at,
        )
        await query.execute(session=session)

    async def save(self, session: AsyncSession, at: Optional[Timestamp] = None) -> SelfRelationshipManager:
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)
        (
            peer_ids_present_both,
            peer_ids_present_local_only,
            peer_ids_present_database_only,
            peers_database,
        ) = await self._fetch_relationship_ids(session=session)

        # Update the relationships in the database that shouldn't be here.
        for peer_id in peer_ids_present_database_only:
            await self.remove_in_db(peer_id=peer_id, peer_data=peers_database[peer_id], at=save_at, session=session)

        # Create the new relationship that are not present in the database
        #  and Compare the existing one
        for rel in await self.get_relationships(session=session):
            if rel.peer_id in peer_ids_present_local_only:
                await rel.save(at=save_at, session=session)

            elif rel.peer_id in peer_ids_present_both:
                if properties_not_matching := rel.compare_properties_with_data(data=peers_database[rel.peer_id]):
                    await rel.update(
                        at=save_at,
                        properties_to_update=properties_not_matching,
                        data=peers_database[rel.peer_id],
                        session=session,
                    )

        return self

    async def delete(
        self,
        session: AsyncSession,
        at: Optional[Timestamp] = None,
    ):
        """Delete all the relationships."""

        delete_at = Timestamp(at)

        await self._fetch_relationships(at=delete_at, session=session)

        for rel in await self.get_relationships(session=session):
            await rel.delete(at=delete_at, session=session)

    async def to_graphql(
        self,
        session: AsyncSession,
        fields: Optional[dict] = None,
    ) -> Union[dict, None]:
        # NOTE Need to investigate when and why we are passing the peer directly here, how do we account for many relationship
        if self.schema.cardinality == "many":
            raise TypeError("to_graphql is not available for relationship with multiple cardinality")

        relationships = await self.get_relationships(session=session)
        if not relationships:
            return None

        return await relationships[0].to_graphql(fields=fields, session=session)
