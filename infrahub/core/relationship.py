from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Union, Dict, Any, Iterator, Generator, TypeVar

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to
from infrahub.exceptions import ValidationError
from infrahub.utils import intersection

from infrahub.core.query.relationship import (
    RelationshipCreateQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipGetQuery,
    RelationshipPeerData,
)
from infrahub.core.property import NodePropertyMixin, FlagPropertyMixin

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import RelationshipSchema, NodeSchema

# RELATIONSHIPS_MAPPING = {"Relationship": Relationship}

SelfRelationship = TypeVar("SelfRelationship", bound="Relationship")


class Relationship(FlagPropertyMixin, NodePropertyMixin):

    rel_type: str = "IS_RELATED"

    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp = None,
        node: Node = None,
        node_id: str = None,
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

    def _process_data(self, data: Union[Dict, RelationshipPeerData, str]):

        self.data = data

        prop_prefix = "_relation__"

        if isinstance(data, RelationshipPeerData):
            self.peer = data.peer_id

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
                    self.peer = data.get(key, None)
                elif key.startswith(prop_prefix) and hasattr(self, key.replace(prop_prefix, "")):
                    setattr(self, key.replace(prop_prefix, ""), value)

        else:
            self.peer = data

    def new(
        self,
        data: Union[dict, RelationshipPeerData, Any] = None,
        *args,
        **kwargs,
    ) -> SelfRelationship:

        self._process_data(data)

        return self

    def load(
        self,
        id: str = None,
        db_id: int = None,
        updated_at: Union[Timestamp, str] = None,
        data: Union[dict, RelationshipPeerData, Any] = None,
    ) -> SelfRelationship:

        self.id = id
        self.db_id = db_id

        if updated_at:
            self.updated_at = Timestamp(updated_at)

        self._process_data(data)

        return self

    def get_kind(self) -> str:
        """Return the kind of the relationship."""
        return self.schema.kind

    @property
    def node(self) -> Node:
        """Return the node of the relationship."""
        if self._node is None:
            self._get_node()

        return self._node

    def _get_node(self) -> bool:
        from infrahub.core.manager import NodeManager

        self._node = NodeManager.get_one(self.node_id, branch=self.branch, at=self.at)

        if self._node:
            return True

        if not self.schema.default_filter:
            return False

        # if a default_filter is defined, try to query the node by its default filter
        results = NodeManager.query(
            self.schema, filters={self.schema.default_filterr: self.node_id}, branch=self.branch, at=self.at
        )

        if not results:
            return False

        self._node = results[0]
        self.node_id = self._node.id

        return True

    @property
    def peer(self) -> Node:
        """Return the peer of the relationship."""
        if self._peer is None:
            self._get_peer()

        return self._peer if self._peer else None

    @peer.setter
    def peer(self, value: Union[Node, str]):

        if hasattr(value, "_schema"):
            if value.get_kind() != self.schema.peer:
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

    def _get_peer(self):
        from infrahub.core.manager import NodeManager

        self._peer = NodeManager.get_one(self.peer_id, branch=self.branch, at=self.at)

        peer_schema = self.get_peer_schema()
        results = None
        if not self._peer and peer_schema.default_filter:
            results = NodeManager.query(
                peer_schema, filters={peer_schema.default_filter: self.peer_id}, branch=self.branch, at=self.at
            )

        if not results:
            return None

        self._peer = results[0]
        self.peer_id = self._peer.id

    def get_peer_schema(self) -> NodeSchema:
        return registry.get_schema(self.schema.peer)

    def _create(self, at: Timestamp = None):
        """Add a relationship with another object by creating a new relationship node."""

        create_at = Timestamp(at)

        # Assuming nothing is present in the database yet
        # Create a new Relationship node and attach each object to it
        query = RelationshipCreateQuery(
            source=self.node, destination=self.peer, rel=self, branch=self.branch, at=create_at
        ).execute()
        result = query.get_result()

        self.db_id = result.get("rl").id
        self.id = result.get("rl").get("uuid")

    def delete(self, at: Timestamp = None):

        delete_at = Timestamp(at)

        query = RelationshipGetQuery(
            source=self.node, destination=self.peer, rel=self, branch=self.branch, at=delete_at
        ).execute()
        result = query.get_result()

        # when we remove a relationship we need to :
        # - Update the existing relationship if we are on the same branch
        # - Create a new rel of type DELETED in the right branch

        if rel_ids_to_update := [rel.id for rel in result.get_rels() if rel.get("branch") == self.branch.name]:
            update_relationships_to(rel_ids_to_update, to=delete_at)

        RelationshipDeleteQuery(
            rel=self, source=self.node, destination=self.peer, branch=self.branch, at=delete_at
        ).execute()

    def save(self, at: Timestamp = None) -> SelfRelationship:
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)

        if not self.id:
            return self._create(at=save_at)

        # UPDATE NOT SUPPORTED FOR NOW
        return self

    def to_graphql(self, fields: dict = None) -> dict:
        """Generate GraphQL Payload for the associated Peer."""

        peer_fields = {key: value for key, value in fields.items() if not key.startswith("_relation")}
        response = self.peer.to_graphql(fields=peer_fields)

        if "_relation__updated_at" in fields:
            response["_relation__updated_at"] = self.updated_at.to_graphql()

        return response


class RelationshipManager:
    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        data: Union[Dict, List, str] = None,
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

        self.relationships: List[Relationship] = []

        # FIXME, we are prefetching all the relationship by default
        # Ideally we should have a lazy implementation here to speed things up
        if data is None:
            self._fetch_relationships()
            return

        # Data can be
        #  - A String, pass it to one relationsip object
        #  - A Dict, pass it to one relationship object
        #  - A list of str or dict, pass it to multiple objects
        if not isinstance(data, list):
            data = [data]

        for item in data:

            if not isinstance(item, (self.rel_class, str, dict)) and not hasattr(item, "_schema"):
                raise ValidationError({self.name: f"Invalid data provided to form a relationship {item}"})

            self.relationships.append(
                self.rel_class(schema=self.schema, branch=self.branch, at=self.at, node=self.node).new(data=item)
            )

    def get_kind(self) -> str:
        return self.schema.kind

    def __iter__(self):
        if self.schema.cardinality == "one":
            raise TypeError("relationship with single cardinality are not iterable")

        return iter(self.relationships)

    @property
    def peer(self) -> Node:
        if self.schema.cardinality == "many":
            raise TypeError("peer is not available for relationship with multiple cardinality")

        if not self.relationships:
            return None

        return self.relationships[0].peer

    def _fetch_relationship_ids(
        self, at: Timestamp = None
    ) -> Tuple[List[str], List[str], List[str], Dict[str, RelationshipPeerData]]:
        """Fetch the latest relationships from the database and returns :
        - the list of nodes present on both sides
        - the list of nodes present only locally
        - the list of nodes present only in the database
        """

        current_peer_ids = [rel.peer_id for rel in self.relationships]

        query = RelationshipGetPeerQuery(
            source=self.node,
            at=at or self.at,
            rel=self.rel_class(schema=self.schema, branch=self.branch, node=self.node),
        ).execute()

        peers_database: dict = {peer.peer_id: peer for peer in query.get_peers()}
        peer_ids = list(peers_database.keys())

        # Calculate which peer should be added or removed
        peer_ids_present_both = intersection(current_peer_ids, peer_ids)
        peer_ids_present_local_only = list(set(current_peer_ids) - set(peer_ids_present_both))
        peer_ids_present_database_only = list(set(peer_ids) - set(peer_ids_present_both))

        return peer_ids_present_both, peer_ids_present_local_only, peer_ids_present_database_only, peers_database

    def _fetch_relationships(self, at: Timestamp = None):
        """Fetch the latest relationships from the database and update the local cache."""

        _, peer_ids_present_local_only, peer_ids_present_database_only, peers_database = self._fetch_relationship_ids(
            at=at
        )

        for peer_id in peer_ids_present_local_only:
            self.remove(peer_id)

        for peer_id in peer_ids_present_database_only:
            self.relationships.append(
                Relationship(
                    schema=self.schema,
                    branch=self.branch,
                    at=at or self.at,
                    node=self.node,
                ).load(data=peers_database[peer_id])
            )

    def get(self) -> Union[Relationship, List[Relationship]]:
        if self.schema.cardinality == "one":
            return self.relationships[0]

        return self.relationships

    def update(self, data: Union[List[str], List[Node], str, Node]) -> bool:
        """Replace and Update the list of relationships with this one."""
        if not isinstance(data, list):
            data = [data]

        # Reset the list of relationship and save the previous one to see if we can reuse some
        previous_relationships = {rel.peer.id: rel for rel in self.relationships}
        self.relationships = []

        for item in data:
            if not isinstance(item, (self.rel_class, str, dict)) and not hasattr(item, "_schema"):
                raise ValidationError({self.name: f"Invalid data provided to form a relationship {item}"})

            if hasattr(item, "_schema") and item.id in previous_relationships:
                self.relationships.append(previous_relationships[item.id])
                continue

            if isinstance(item, str) and item in previous_relationships:
                self.relationships.append(previous_relationships[item])
                continue

            # If the item is not present in the previous list of relationship, we create a new one.
            self.relationships.append(
                self.rel_class(schema=self.schema, branch=self.branch, at=self.at, node=self.node).new(data=item)
            )

        new_rel_ids = [rel.peer_id for rel in self.relationships]

        # Return True if the list of relationship has been updated
        changed = sorted(new_rel_ids) != sorted(list(previous_relationships.keys()))
        return changed

    def remove(self, peer_id: str, update_db: bool = False):
        """Remote a peer id from the local relationships list,
        need to investigate if and when we should update the relationship in the database."""
        for idx, rel in enumerate(self.relationships):
            if rel.peer_id != peer_id:
                continue

            if update_db:
                rel.delete()

            self.relationships.pop(idx)
            return True

        raise Exception("Relationship not found ... unexpected")

    def save(self, at: Timestamp = None):
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)
        _, peer_ids_present_local_only, peer_ids_present_database_only, peers_database = self._fetch_relationship_ids()

        # Update the relationships in the database
        for peer_id in peer_ids_present_database_only:
            self.remove(peer_id=peer_id, update_db=True)

        for rel in self.relationships:
            if rel.peer_id in peer_ids_present_local_only:
                rel.save(at=save_at)

        return True

    def delete(self, at: Timestamp = None):
        """Delete all the relationships."""

        delete_at = Timestamp(at)

        self._fetch_relationships(at=delete_at)

        for rel in self.relationships:
            rel.delete(at=delete_at)

    def to_graphql(self, fields: dict = None) -> dict:
        # NOTE Need to investigate when and why we are passing the peer directly here, how do we account for many relationship
        if self.schema.cardinality == "many":
            raise TypeError("to_graphql is not available for relationship with multiple cardinality")

        if not self.relationships:
            return None

        return self.relationships[0].to_graphql(fields=fields)
