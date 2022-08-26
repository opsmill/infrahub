from __future__ import annotations

from ctypes import Union
from typing import TYPE_CHECKING, List, Tuple, Union

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to
from infrahub.exceptions import ValidationError
from infrahub.utils import intersection

from .query import (
    RelationshipCreateQuery,
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
    RelationshipGetQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import RelationshipSchema

# RELATIONSHIPS_MAPPING = {"Relationship": Relationship}


class Relationship:

    rel_type = "IS_RELATED"

    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        name: str = None,
        id=None,
        db_id: int = None,
        data=None,
        *args,
        **kwargs,
    ):

        self.id = kwargs.get("id", None)

        self.id = id
        self.db_id = db_id

        self.name = name
        self.schema = schema
        self.node = node
        self.branch = branch
        self.at = at

        self.data = data

        self.peer_id = None
        self._peer = None

        # Validate Data
        # Can be a list of UUIDs or a list of dict
        # TODO add support for default value
        peer = None
        if isinstance(data, dict) and "peer" in data:
            peer = data.get("peer", None)
        else:
            peer = data

        self.validate(peer)

    def validate(self, peer: Union[Node, str]) -> bool:

        if hasattr(peer, "_schema"):
            if peer.get_kind() != self.schema.peer:
                raise ValidationError(
                    {self.name: f"Got an object of type {peer.get_kind()} instead of {self.schema.peer}"}
                )

            self._peer = peer
            self.peer_id = peer.id
            return True

        if isinstance(peer, str):
            self.peer_id = peer
            return True

        raise ValidationError({self.name: f"Unsupported type ({type(peer)}) must be a string or a node object"})

    def get_kind(self) -> str:
        """Return the kind of the relationship."""
        return self.schema.kind

    @property
    def peer(self) -> Node:
        """Return the peer of the relationship."""
        if self._peer is None:
            self._get_peer()

        return self._peer if self._peer else None

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

    def get_peer_schema(self):
        return registry.get_schema(self.schema.peer)

    def _create(self, at: Timestamp = None):
        """Add a relationship with another object by creating a new relationship node."""

        create_at = Timestamp(at)

        # Assuming nothing is present in the database yet
        # Create a new Relationship node and attach each object to it
        query = RelationshipCreateQuery(source=self.node, destination=self.peer, rel=self, at=create_at).execute()
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

        delete_query = RelationshipDeleteQuery(
            rel=self, source=self.node, destination=self.peer, branch=self.branch, at=delete_at
        ).execute()

    def save(self, at: Timestamp = None):
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)

        if not self.id:
            return self._create(at=save_at)

        # UPDATE NOT SUPPORTED FOR NOW
        return True


class RelationshipManager:
    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        name: str = None,
        data=None,
        *args,
        **kwargs,
    ):

        self.name = name
        self.schema = schema
        self.node = node
        self.branch = branch
        self.at = at

        # TODO Ideally this informaiton should come from the Schema
        self.rel_class = Relationship

        self.relationships = []

        if data is None:
            self._fetch_relationships()
            return

        # Data can be
        # A String, pass it to one relationsip object
        # A Dict, pass it to one relationship object
        # A list of str or dict, pass it to multiple objects
        if not isinstance(data, list):
            data = [data]

        for item in data:

            if not isinstance(item, (self.rel_class, str, dict)) and not hasattr(item, "_schema"):
                raise ValidationError({self.name: f"Invalid data provided to form a relationship {item}"})

            self.relationships.append(
                self.rel_class(
                    schema=self.schema, branch=self.branch, at=self.at, node=self.node, name=self.name, data=item
                )
            )

    def get_kind(self):
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

    def _fetch_relationship_ids(self, at: Timestamp = None) -> Tuple[List[str, List[str], List[str]]]:
        """Fetch the latest relationships from the database and returns :
        - the list of nodes present on both sides
        - the list of nodes present only locally
        - the list of nodes present only in the database
        """

        current_peer_ids = [rel.peer_id for rel in self.relationships]

        query = RelationshipGetPeerQuery(
            source_id=self.node.id,
            schema=self.schema,
            branch=self.branch,
            at=at or self.at,
            rel_type=self.rel_class.rel_type,
        )
        query.execute()
        peer_ids = query.get_peer_ids() or []

        # Calculate which peer should be added or removed
        peers_present_both = intersection(current_peer_ids, peer_ids)
        peers_present_local = list(set(current_peer_ids) - set(peers_present_both))
        peers_present_database = list(set(peer_ids) - set(peers_present_both))

        return peers_present_both, peers_present_local, peers_present_database

    def _fetch_relationships(self, at: Timestamp = None):
        """Fetch the latest relationships from the database and update the local cache."""

        _, peers_present_local, peers_present_database = self._fetch_relationship_ids(at=at)

        for peer_id in peers_present_local:
            self.remove(peer_id)

        for peer_id in peers_present_database:
            self.relationships.append(
                Relationship(
                    schema=self.schema,
                    branch=self.branch,
                    at=at or self.at,
                    node=self.node,
                    name=self.name,
                    data=peer_id,
                )
            )

    def get(self) -> Union[Node, List[Relationship]]:
        if self.schema.cardinality == "one":
            return self.peer

        return [rel.peer for rel in self.relationships]

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

            self.relationships.append(
                self.rel_class(
                    schema=self.schema, branch=self.branch, at=self.at, node=self.node, name=self.name, data=item
                )
            )

        new_rel_ids = [rel.peer.id for rel in self.relationships]

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
        peers_present_both, peers_present_local, peers_present_database = self._fetch_relationship_ids()

        # Update the relationships in the database
        for peer_id in peers_present_database:
            self.remove(peer_id=peer_id, update_db=True)

        for rel in self.relationships:
            if rel.peer_id in peers_present_local:
                rel.save(at=save_at)

        return True

    def delete(self, at: Timestamp = None):
        """Delete all the relationships."""

        delete_at = Timestamp(at)

        self._fetch_relationships(at=delete_at)

        for rel in self.relationships:
            rel.delete(at=delete_at)

    def to_graphql(self, fields: dict = None) -> dict:

        peer = self.peer
        if not peer:
            return None

        return peer.to_graphql(fields=fields)
