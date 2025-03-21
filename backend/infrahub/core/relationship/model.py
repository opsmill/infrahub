from __future__ import annotations

import asyncio
import copy
import sys
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    Sequence,
    TypeVar,
    overload,
)

from infrahub_sdk.utils import intersection, is_valid_uuid
from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel, Field

from infrahub.core import registry
from infrahub.core.changelog.models import ChangelogRelationshipMapper
from infrahub.core.constants import BranchSupportType, InfrahubKind, RelationshipKind
from infrahub.core.property import (
    FlagPropertyMixin,
    NodePropertyData,
    NodePropertyMixin,
)
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
from infrahub.exceptions import Error, NodeNotFoundError, ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes, RelationshipSchema
    from infrahub.database import InfrahubDatabase


PeerType = TypeVar("PeerType")

PREFIX_PROPERTY = "_relation__"
INDEX_DEFAULT_STOP = sys.maxsize


class RelationshipCreateData(BaseModel):
    uuid: str
    name: str
    destination_id: str
    branch: str | None = None
    branch_level: int
    branch_support: str | None = None
    direction: str
    status: str
    is_protected: bool
    is_visible: bool
    hierarchical: str | None = None
    source_prop: list[NodePropertyData] = Field(default_factory=list)
    owner_prop: list[NodePropertyData] = Field(default_factory=list)


@dataclass
class RelationshipUpdateDetails:
    peers_database: dict[str, RelationshipPeerData]
    peer_ids_present_both: list[str]
    peer_ids_present_local_only: list[str]
    peer_ids_present_database_only: list[str]


class Relationship(FlagPropertyMixin, NodePropertyMixin):
    rel_type: str = "IS_RELATED"

    def __init__(
        self,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp | None = None,
        node: Node | None = None,
        node_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        if not node and not node_id:
            raise ValueError("Either node or node_id must be provided.")

        self.schema = schema
        self.name = schema.name

        self.branch = branch
        self.at = Timestamp(at)

        self._node = node
        self._node_id: str | None = node_id

        self.id: UUID | None = None
        self.db_id: str | None = None
        self.updated_at: Timestamp | None = None

        self._peer: Node | str | None = None
        self.peer_id: str | None = None
        self.peer_hfid: list[str] | None = None
        self.data: dict | RelationshipPeerData | str | None = None

        self.from_pool: dict[str, Any] | None = None

        self._init_node_property_mixin(kwargs=kwargs)
        self._init_flag_property_mixin(kwargs=kwargs)

    def __hash__(self) -> int:
        """Generate a hash based on the Peer and the properties."""

        values = [self.id, self.db_id, self.peer_id]
        for prop_name in self._flag_properties:
            values.append(getattr(self, prop_name))

        for prop_name in self._node_properties:
            values.append(getattr(self, f"{prop_name}_id"))

        return hash(tuple(values))

    def get_peer_id(self) -> str:
        if not self.peer_id:
            raise ValueError("Relationship has not been initialized yet")

        return self.peer_id

    def get_peer_kind(self) -> str:
        if not self._peer or isinstance(self._peer, str):
            return self.schema.peer

        return self._peer.get_kind()

    @property
    def node_id(self) -> str:
        if self._node_id:
            return self._node_id
        if self._node:
            return self._node.get_id()
        raise ValueError("Cannot get ID for relationship node")

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Returns:
            Branch:
        """
        if self.schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self.branch

    async def _process_data(self, data: dict | RelationshipPeerData | str) -> None:
        self.data = data

        if isinstance(data, RelationshipPeerData):
            await self.set_peer(value=str(data.peer_id))

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
                elif key == "hfid" and self.peer_id is None:
                    self.peer_hfid = value
                elif key.startswith(PREFIX_PROPERTY) and key.replace(PREFIX_PROPERTY, "") in self._flag_properties:
                    setattr(self, key.replace(PREFIX_PROPERTY, ""), value)
                elif key.startswith(PREFIX_PROPERTY) and key.replace(PREFIX_PROPERTY, "") in self._node_properties:
                    setattr(self, key.replace(PREFIX_PROPERTY, ""), value)
                elif key == "from_pool":
                    self.from_pool = value

        else:
            await self.set_peer(value=data)

    async def new(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        data: dict | RelationshipPeerData | Any = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> Relationship:
        await self._process_data(data=data)

        return self

    async def load(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        id: UUID | None = None,
        db_id: str | None = None,
        updated_at: Timestamp | str | None = None,
        data: dict | RelationshipPeerData | Any = None,
    ) -> Self:
        hash_before = hash(self)

        self.id = id or self.id
        self.db_id = db_id or self.db_id

        await self._process_data(data=data)

        if updated_at and hash(self) != hash_before:
            self.updated_at = Timestamp(updated_at)

        return self

    def get_kind(self) -> str:
        """Return the kind of the relationship."""
        return self.schema.kind

    async def get_node(self, db: InfrahubDatabase) -> Node:
        """Return the node of the relationship."""
        if self._node:
            return self._node

        node: Node = await registry.manager.get_one_by_id_or_default_filter(
            db=db,
            id=self.node_id,
            kind=self.schema.kind.value,
            branch=self.branch,
            at=self.at,
            include_owner=True,
            include_source=True,
        )
        self._node = node
        self._node_id = self._node.id
        return node

    async def set_peer(self, value: str | Node) -> None:
        if isinstance(value, str):
            self.peer_id = value
        else:
            self._peer = value
            self.peer_id = value.get_id()

    @overload
    async def get_peer(self, db: InfrahubDatabase, peer_type: type[PeerType]) -> PeerType: ...

    @overload
    async def get_peer(self, db: InfrahubDatabase, peer_type: None = ...) -> Node: ...

    async def get_peer(self, db: InfrahubDatabase, peer_type: type[PeerType] | None = None) -> Any:  # noqa: ARG002
        """Return the peer of the relationship."""
        if self._peer is None:
            await self._get_peer(db=db)

        if isinstance(self._peer, str):
            await self._get_peer(db=db)

        if self._peer is None or isinstance(self._peer, str):
            raise NodeNotFoundError(
                branch_name=self.branch.name, node_type=self.schema.peer, identifier=self.get_peer_id()
            )
        return self._peer

    async def _get_peer(self, db: InfrahubDatabase) -> None:
        peer: Node
        try:
            if self.peer_hfid:
                peer = await registry.manager.get_one_by_hfid(
                    db=db,
                    hfid=self.peer_hfid,
                    kind=self.schema.peer,
                    raise_on_error=True,
                    at=self.at,
                    branch=self.branch,
                    include_source=True,
                    include_owner=True,
                    prefetch_relationships=False,
                    branch_agnostic=self.schema.branch is BranchSupportType.AGNOSTIC,
                )
            else:
                peer = await registry.manager.get_one_by_id_or_default_filter(
                    db=db,
                    id=self.get_peer_id(),
                    kind=self.schema.peer,
                    branch=self.branch,
                    at=self.at,
                    include_owner=True,
                    include_source=True,
                    branch_agnostic=self.schema.branch is BranchSupportType.AGNOSTIC,
                )
        except NodeNotFoundError:
            self._peer = None
            return

        self._peer = peer
        self.peer_id = self._peer.id

    def get_peer_schema(self, db: InfrahubDatabase) -> MainSchemaTypes:
        return db.schema.get(name=self.schema.peer, branch=self.branch, duplicate=False)

    def compare_properties_with_data(self, data: RelationshipPeerData) -> list[str]:
        different_properties = []

        if hasattr(self, "_flag_properties"):
            for property_name in self._flag_properties:
                memory_value = getattr(self, property_name, None)
                database_prop = data.properties.get(property_name)
                database_value = database_prop.value if database_prop else None
                if memory_value != database_value:
                    different_properties.append(property_name)

        if hasattr(self, "_node_properties"):
            for property_name in self._node_properties:
                memory_value = getattr(self, f"{property_name}_id", None)
                database_prop = data.properties.get(property_name)
                database_value = database_prop.value if database_prop else None
                if memory_value != database_value:
                    different_properties.append(property_name)

        return different_properties

    async def _create(self, db: InfrahubDatabase, at: Timestamp | None = None) -> None:
        """Add a relationship with another object by creating a new relationship node."""

        create_at = Timestamp(at)

        # Assuming nothing is present in the database yet
        # Create a new Relationship node and attach each object to it
        node = await self.get_node(db=db)
        peer = await self.get_peer(db=db)
        branch = self.get_branch_based_on_support_type()

        query = await RelationshipCreateQuery.init(
            db=db, source=node, destination=peer, rel=self, branch=branch, at=create_at
        )
        await query.execute(db=db)
        result = query.get_result()
        if not result:
            return

        self.db_id = result.get("rl").element_id
        self.id = result.get("rl").get("uuid")

    async def update(
        self,
        db: InfrahubDatabase,
        properties_to_update: list[str],
        data: RelationshipPeerData,
        at: Timestamp | None = None,
    ) -> None:
        """Update the properties of an existing relationship."""

        update_at = Timestamp(at)
        branch = self.get_branch_based_on_support_type()

        rel_ids_to_update = []
        for prop_name, prop in data.properties.items():
            if prop_name in properties_to_update and prop.rel.branch == self.branch.name:
                rel_ids_to_update.append(prop.rel.db_id)

        if rel_ids_to_update:
            await update_relationships_to(rel_ids_to_update, to=update_at, db=db)

        node = await self.get_node(db=db)

        query = await RelationshipUpdatePropertyQuery.init(
            db=db,
            source=node,
            rel=self,
            properties_to_update=properties_to_update,
            data=data,
            branch=branch,
            at=update_at,
        )
        await query.execute(db=db)

    async def delete(self, db: InfrahubDatabase, at: Timestamp | None = None) -> None:
        delete_at = Timestamp(at)

        node = await self.get_node(db=db)
        peer = await self.get_peer(db=db)

        branch = self.get_branch_based_on_support_type()

        get_query = await RelationshipGetQuery.init(
            db=db, source=node, destination=peer, rel=self, branch=self.branch, at=delete_at
        )
        await get_query.execute(db=db)
        result = get_query.get_result()
        if not result:
            raise Error(
                f"Unable to find the relationship to delete. id: {self.id}, source: {node.id}, destination: {peer.id}"
            )

        # when we remove a relationship we need to :
        # - Update the existing relationship if we are on the same branch
        # - Create a new rel of type DELETED in the right branch

        if rel_ids_to_update := [rel.element_id for rel in result.get_rels() if rel.get("branch") == branch.name]:
            await update_relationships_to(rel_ids_to_update, to=delete_at, db=db)

        delete_query = await RelationshipDeleteQuery.init(
            db=db, rel=self, source_id=node.id, destination_id=peer.id, branch=branch, at=delete_at
        )
        await delete_query.execute(db=db)

    async def resolve(self, db: InfrahubDatabase) -> None:
        """Resolve the peer of the relationship."""

        if self._peer is not None:
            return

        if self.peer_id and not is_valid_uuid(self.peer_id):
            peer = await registry.manager.get_one_by_default_filter(
                db=db, id=self.peer_id, branch=self.branch, kind=self.schema.peer, fields={"display_label": None}
            )
            if peer:
                await self.set_peer(value=peer)

        if not self.peer_id and self.peer_hfid:
            peer_schema = db.schema.get(name=self.schema.peer, branch=self.branch)
            kind = (
                self.data["kind"]
                if isinstance(self.data, dict) and "kind" in self.data and peer_schema.is_generic_schema
                else self.schema.peer
            )
            peer = await registry.manager.get_one_by_hfid(
                db=db,
                hfid=self.peer_hfid,
                branch=self.branch,
                kind=kind,
                fields={"display_label": None},
                raise_on_error=True,
            )
            await self.set_peer(value=peer)

        if not self.peer_id and self.from_pool and "id" in self.from_pool:
            pool_id = str(self.from_pool.get("id"))
            pool = await registry.manager.get_one(db=db, id=pool_id, branch=self.branch)

            if not pool:
                raise NodeNotFoundError(
                    node_type=InfrahubKind.RESOURCEPOOL,
                    identifier=pool_id,
                    branch_name=self.branch.name,
                    message=f"Unable to find the pool to generate a node for the relationship {self.name!r} on {self.node_id!r}",
                )

            data_from_pool = copy.deepcopy(self.from_pool)
            del data_from_pool["id"]

            if "identifier" not in data_from_pool and self._node:
                hfid_str = await self._node.get_hfid_as_string(db=db, include_kind=True)
                if hfid_str:
                    data_from_pool["identifier"] = f"hfid={hfid_str} rel={self.name}"

            assigned_peer: Node = await pool.get_resource(db=db, branch=self.branch, **data_from_pool)  # type: ignore[attr-defined]
            await self.set_peer(value=assigned_peer)
            self.set_source(value=pool.id)

    async def save(self, db: InfrahubDatabase, at: Timestamp | None = None) -> Self:
        """Create or Update the Relationship in the database."""

        save_at = Timestamp(at)

        if not self.id:
            await self._create(at=save_at, db=db)
            return self

        return self

    async def to_graphql(self, fields: dict | None, db: InfrahubDatabase, related_node_ids: set | None = None) -> dict:
        """Generate GraphQL Payload for the associated Peer."""

        if not fields:
            peer_fields, rel_fields = {}, {}
        else:
            peer_fields = {
                key: value
                for key, value in fields.items()
                if not key.startswith(PREFIX_PROPERTY) or not key == "__typename"
            }
            rel_fields = {
                key.replace(PREFIX_PROPERTY, ""): value
                for key, value in fields.items()
                if key.startswith(PREFIX_PROPERTY)
            }

        peer = await self.get_peer(db=db)
        response = await peer.to_graphql(fields=peer_fields, db=db, related_node_ids=related_node_ids)

        for field_name in rel_fields.keys():
            if field_name == "updated_at" and self.updated_at:
                response[f"{PREFIX_PROPERTY}{field_name}"] = await self.updated_at.to_graphql(db=db)

            if field_name in self._node_properties:
                node_prop_getter = getattr(self, f"get_{field_name}")
                node_prop = await node_prop_getter(db=db)
                if not node_prop:
                    response[f"{PREFIX_PROPERTY}{field_name}"] = None
                else:
                    response[f"{PREFIX_PROPERTY}{field_name}"] = await node_prop.to_graphql(
                        db=db, fields=rel_fields[field_name], related_node_ids=related_node_ids
                    )
            if field_name in self._flag_properties:
                response[f"{PREFIX_PROPERTY}{field_name}"] = getattr(self, field_name)

        if fields and "__typename" in fields:
            response["__typename"] = f"Related{peer.get_kind()}"

        return response

    async def get_create_data(self, db: InfrahubDatabase) -> RelationshipCreateData:
        branch = self.get_branch_based_on_support_type()

        await self.resolve(db=db)

        peer = await self.get_peer(db=db)
        data = RelationshipCreateData(
            uuid=str(UUIDT()),
            name=self.schema.get_identifier(),
            branch=branch.name,
            destination_id=peer.id,
            status="active",
            direction=self.schema.direction.value,
            branch_level=self.branch.hierarchy_level,
            branch_support=self.schema.branch.value if self.schema.branch else None,
            hierarchical=self.schema.hierarchical,
            is_protected=self.is_protected,
            is_visible=self.is_visible,
        )
        if hasattr(self, "source_id") and self.source_id:
            data.source_prop.append(NodePropertyData(name="source", peer_id=str(self.source_id)))

        if hasattr(self, "owner_id") and self.owner_id:
            data.owner_prop.append(NodePropertyData(name="owner", peer_id=str(self.owner_id)))

        return data


class RelationshipValidatorList:
    """Provides a list/set like interface to the RelationshipManager's _relationships but with validation against min/max count and no duplicates.

    Raises:
        ValidationError: If the number of relationships is not within the min and max count.
    """

    def __init__(self, *relationships: Relationship, name: str, min_count: int = 0, max_count: int = 0) -> None:
        """Initialize list for Relationship but with validation against min/max count.

        Args:
            min_count (int, optional): Min count of relationships required. Defaults to 0.
            max_count (int, optional): Max count of relationships allowed. Defaults to 0. 0 provides no limit.

        Raises:
            ValidationError: The number of relationships is not within the min and max count.
        """
        if max_count < min_count:
            raise ValidationError({"msg": "max_count must be greater than min_count"})
        self.min_count: int = min_count
        self.max_count: int = max_count
        self.name = name

        self._relationships: list[Relationship] = [rel for rel in relationships if isinstance(rel, Relationship)]
        self._relationships_count: int = len(self._relationships)

        # Validate the initial relationships count is within the min and max count if relationships were provided
        # Allow this class to be instantiated without relationships
        if self._relationships:
            if self.max_count and self._relationships_count > self.max_count:
                self._raise_too_many()
            if self.min_count and self._relationships_count < self.min_count:
                self._raise_too_few()

    def __contains__(self, item: Relationship) -> bool:
        return item in self._relationships

    def __hash__(self) -> int:
        return hash(self._relationships)

    def __iter__(self) -> Iterator[Relationship]:
        return iter(self._relationships)

    def __getitem__(self, index: int) -> Relationship:
        return self._relationships[index]

    def __setitem__(self, index: int, value: Relationship) -> None:
        if value in self._relationships:
            raise ValidationError({value.name: "Relationship already exists in the list"})
        if not isinstance(value, Relationship):
            raise ValidationError("RelationshipValidatorList only accepts Relationship objects")
        self._relationships[index] = value

    def __delitem__(self, index: int) -> None:
        if self._relationships_count - 1 < self.min_count:
            self._raise_too_few()
        del self._relationships[index]

    def __len__(self) -> int:
        length = len(self._relationships)
        if length != self._relationships_count:
            self._relationships_count = length
        return length

    def __repr__(self) -> str:
        return repr(self._relationships)

    def append(self, rel: Relationship) -> None:
        # Do not do anything if the relationship is already present
        if rel in self._relationships:
            return
        if not isinstance(rel, Relationship):
            raise ValidationError("RelationshipValidatorList only accepts Relationship objects")

        # If the max_count is greater than 0 then validate
        if self.max_count and self._relationships_count + 1 > self.max_count:
            self._raise_too_many()

        self._relationships.append(rel)
        self._relationships_count += 1

    def clear(self) -> None:
        self._relationships.clear()
        self._relationships_count = len(self._relationships)

    def extend(self, iterable: Iterable[Relationship]) -> None:
        # Filter down to only Relationship objects and remove duplicates
        relationships = [rel for rel in iterable if isinstance(rel, Relationship) and rel not in self._relationships]
        rel_len = len(relationships)
        # If the max_count is greater than 0 then validate
        if self.max_count and self._relationships_count + rel_len > self.max_count:
            self._raise_too_many()

        self._relationships.extend(relationships)
        self._relationships_count += rel_len

    def get(self, index: int) -> Relationship:
        return self._relationships[index]

    def index(self, value: Relationship, start: int = 0, stop: int = INDEX_DEFAULT_STOP) -> int:
        return self._relationships.index(value, start, stop)

    def insert(self, index: int, value: Relationship) -> None:
        if value in self._relationships:
            return
        if not isinstance(value, Relationship):
            raise ValidationError("RelationshipValidatorList only accepts Relationship objects")
        if self.max_count and self._relationships_count + 1 > self.max_count:
            self._raise_too_many()
        self._relationships.insert(index, value)
        self._relationships_count += 1

    def pop(self, idx: int = -1) -> Relationship:
        if self.min_count and self._relationships_count - 1 < self.min_count:
            self._raise_too_few()

        result = self._relationships.pop(idx)
        self._relationships_count -= 1
        return result

    def remove(self, value: Relationship) -> None:
        if self.min_count and self._relationships_count - 1 < self.min_count:
            self._raise_too_few()
        self._relationships.remove(value)
        self._relationships_count -= 1

    def as_list(self) -> list[Relationship]:
        return self._relationships

    def _raise_too_few(self) -> None:
        raise ValidationError({self.name: f"Too few relationships, min {self.min_count}"})

    def _raise_too_many(self) -> None:
        raise ValidationError({self.name: f"Too many relationships, max {self.max_count}"})

    def validate_min(self) -> None:
        if not self.min_count:
            return
        if self._relationships_count < self.min_count:
            raise ValidationError({self.name: f"Too few relationships, min {self.min_count}"})

    def validate_max(self) -> None:
        if not self.max_count:
            return
        if self._relationships_count > self.max_count:
            raise ValidationError({self.name: f"Too many relationships, max {self.max_count}"})

    def validate(self) -> None:
        self.validate_min()
        self.validate_max()


class RelationshipManager:
    def __init__(self, schema: RelationshipSchema, branch: Branch, at: Timestamp, node: Node) -> None:
        self.schema: RelationshipSchema = schema
        self.name: str = schema.name
        self.node: Node = node
        self.branch: Branch = branch
        self.at = at

        # TODO Ideally this information should come from the Schema
        self.rel_class = Relationship

        self._relationships: RelationshipValidatorList = RelationshipValidatorList(
            name=self.schema.name,
            min_count=0 if self.schema.optional else self.schema.min_count,
            max_count=self.schema.max_count,
        )
        self._relationship_id_details: RelationshipUpdateDetails | None = None
        self.has_fetched_relationships: bool = False
        self.lock = asyncio.Lock()

    @classmethod
    async def init(
        cls,
        db: InfrahubDatabase,
        schema: RelationshipSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        data: dict | list | str | None = None,
    ) -> RelationshipManager:
        rm = cls(schema=schema, branch=branch, at=at, node=node)

        # By default we are not loading the relationships
        # These will be accessed on demand, if needed
        if data is None:
            return rm

        # Data can be
        #  - A String, pass it to one relationsip object
        #  - A dict, pass it to one relationship object
        #  - A list of str or dict, pass it to multiple objects
        if not isinstance(data, list):
            data = [data]

        await rm._validate_hierarchy()

        for item in data:
            if not isinstance(item, rm.rel_class | str | dict) and not hasattr(item, "_schema"):
                raise ValidationError({rm.name: f"Invalid data provided to form a relationship {item}"})

            rel = rm.rel_class(schema=rm.schema, branch=rm.branch, at=rm.at, node=rm.node)
            await rel.new(db=db, data=item)

            rm._relationships.append(rel)

        rm.has_fetched_relationships = True

        return rm

    def get_kind(self) -> str:
        return self.schema.kind

    def __iter__(self) -> Iterator[Relationship]:
        if self.schema.cardinality == "one":
            raise TypeError("relationship with single cardinality are not iterable")

        if not self.has_fetched_relationships:
            raise LookupError("you can't iterate over the relationships before the cache has been populated.")

        return iter(self._relationships)

    def get_one(self) -> Relationship | None:
        if not self.has_fetched_relationships:
            raise LookupError("you can't get a relationship before the cache has been populated.")

        return self._relationships[0] if self._relationships else None

    def __len__(self) -> int:
        if not self.has_fetched_relationships:
            raise LookupError("you can't count relationships before the cache has been populated.")

        return len(self._relationships)

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType],
        raise_on_error: Literal[False] = ...,
    ) -> PeerType | None: ...

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType],
        raise_on_error: Literal[True],
    ) -> PeerType: ...

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType],
        raise_on_error: bool,
    ) -> PeerType: ...

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: None = ...,
        raise_on_error: Literal[False] = ...,
    ) -> Node | None: ...

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: None = ...,
        raise_on_error: Literal[True] = ...,
    ) -> Node: ...

    @overload
    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: None = ...,
        raise_on_error: bool = ...,
    ) -> Node: ...

    async def get_peer(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType] | None = None,  # noqa: ARG002
        raise_on_error: bool = False,
    ) -> Node | PeerType | None:
        if self.schema.cardinality == "many":
            raise TypeError("peer is not available for relationship with multiple cardinality")

        rels = await self.get_relationships(db=db)
        if not rels and not raise_on_error:
            return None
        if not rels and raise_on_error:
            raise LookupError("Unable to find the peer")

        peer = await rels[0].get_peer(db=db)
        return peer

    @overload
    async def get_peers(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType],
        branch_agnostic: bool = ...,
    ) -> Mapping[str, PeerType]: ...

    @overload
    async def get_peers(
        self,
        db: InfrahubDatabase,
        peer_type: None = None,
        branch_agnostic: bool = ...,
    ) -> Mapping[str, Node]: ...

    async def get_peers(
        self,
        db: InfrahubDatabase,
        peer_type: type[PeerType] | None = None,  # noqa: ARG002
        branch_agnostic: bool = False,
    ) -> Mapping[str, Node | PeerType]:
        rels = await self.get_relationships(db=db, branch_agnostic=branch_agnostic)
        peer_ids = [rel.peer_id for rel in rels if rel.peer_id]
        nodes = await registry.manager.get_many(
            db=db, ids=peer_ids, branch=self.branch, branch_agnostic=branch_agnostic
        )
        return nodes

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Note that if this relationship is Aware and source node is Agnostic, it will return -global- branch.

        Returns:
            Branch:
        """
        if self.schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self.branch

    async def fetch_relationship_ids(
        self,
        db: InfrahubDatabase,
        at: Timestamp | None = None,
        branch_agnostic: bool = False,
        force_refresh: bool = True,
    ) -> RelationshipUpdateDetails:
        """Fetch the latest relationships from the database and returns :
        - the list of nodes present on both sides
        - the list of nodes present only locally
        - the list of nodes present only in the database
        """
        if not force_refresh and self._relationship_id_details is not None:
            return self._relationship_id_details

        current_peer_ids = [rel.get_peer_id() for rel in self._relationships]

        query = await RelationshipGetPeerQuery.init(
            db=db,
            source=self.node,
            at=at or self.at,
            rel=self.rel_class(schema=self.schema, branch=self.branch, node=self.node),
            branch_agnostic=branch_agnostic,
        )
        await query.execute(db=db)

        peers_database: dict = {str(peer.peer_id): peer for peer in query.get_peers()}
        peer_ids = list(peers_database.keys())

        # Calculate which peer should be added or removed
        peer_ids_present_both = intersection(current_peer_ids, peer_ids)
        peer_ids_present_local_only = list(set(current_peer_ids) - set(peer_ids_present_both))
        peer_ids_present_database_only = list(set(peer_ids) - set(peer_ids_present_both))

        self._relationship_id_details = RelationshipUpdateDetails(
            peer_ids_present_both=peer_ids_present_both,
            peer_ids_present_local_only=peer_ids_present_local_only,
            peer_ids_present_database_only=peer_ids_present_database_only,
            peers_database=peers_database,
        )
        return self._relationship_id_details

    async def _fetch_relationships(
        self,
        db: InfrahubDatabase,
        at: Timestamp | None = None,
        branch_agnostic: bool = False,
        force_refresh: bool = True,
    ) -> None:
        """Fetch the latest relationships from the database and update the local cache."""

        details = await self.fetch_relationship_ids(
            at=at, db=db, branch_agnostic=branch_agnostic, force_refresh=force_refresh
        )

        for peer_id in details.peer_ids_present_database_only:
            self._relationships.append(
                await Relationship(
                    schema=self.schema,
                    branch=self.branch,
                    at=at or self.at,
                    node=self.node,
                ).load(db=db, data=details.peers_database[peer_id])
            )

        self.has_fetched_relationships = True

        for peer_id in details.peer_ids_present_local_only:
            await self.remove_locally(peer_id=peer_id, db=db)

    async def get(self, db: InfrahubDatabase) -> Relationship | list[Relationship] | None:
        rels = await self.get_relationships(db=db)

        if self.schema.cardinality == "one" and rels:
            return rels[0]
        if self.schema.cardinality == "one" and not rels:
            return None

        return rels

    async def get_parent(
        self, db: InfrahubDatabase, branch_agnostic: bool = False, force_refresh: bool = False
    ) -> Relationship | None:
        if self.schema.kind == RelationshipKind.PARENT:
            for relationship in await self.get_relationships(
                db=db, branch_agnostic=branch_agnostic, force_refresh=force_refresh
            ):
                # As parent relationships requires cardinality=one there will always only be one relationship
                # here even though it's within a loop
                return relationship

        return None

    async def get_relationships(
        self, db: InfrahubDatabase, branch_agnostic: bool = False, force_refresh: bool = False
    ) -> list[Relationship]:
        # Use lock to avoid concurrent mutations on this object. This may typically happen while querying two nodes
        # having the same parent, with the parent having another extra relationship. Concurrent coroutines will try to
        # add this relationship to this object, and the second one will fail. See https://github.com/opsmill/infrahub/issues/5474.
        # Note it also prevents extra relationships fetching. Ideally, DataLoader would fetch all needed data only once
        # and exporting node to graphql would then not mutate this object.
        async with self.lock:
            if force_refresh or not self.has_fetched_relationships:
                await self._fetch_relationships(db=db, branch_agnostic=branch_agnostic, force_refresh=force_refresh)

        return self._relationships.as_list()

    async def update(self, data: list[str | Node] | dict[str, Any] | str | Node | None, db: InfrahubDatabase) -> bool:
        """Replace and Update the list of relationships with this one."""
        if not isinstance(data, list):
            list_data: Sequence[str | Node | dict[str, Any] | None] = [data]
        else:
            list_data = data

        await self._validate_hierarchy()

        # Reset the list of relationship and save the previous one to see if we can reuse some
        previous_relationships = {rel.peer_id: rel for rel in await self.get_relationships(db=db) if rel.peer_id}
        self._relationships.clear()
        changed = False

        for item in list_data:
            if not isinstance(item, self.rel_class | str | dict | type(None)) and not hasattr(item, "_schema"):
                raise ValidationError({self.name: f"Invalid data provided to form a relationship {item}"})

            if hasattr(item, "_schema"):
                item_id = getattr(item, "id", None)
                if item_id and item_id in previous_relationships:
                    self._relationships.append(previous_relationships[str(item_id)])
                    continue

            if item is None:
                if previous_relationships:
                    for rel in previous_relationships.values():
                        await rel.delete(db=db)
                    changed = True
                continue

            if isinstance(item, str) and item in previous_relationships:
                self._relationships.append(previous_relationships[item])
                continue

            if isinstance(item, dict) and item.get("id", None) in previous_relationships:
                rel = previous_relationships[item["id"]]
                hash_before = hash(rel)
                await rel.load(data=item, db=db)
                if hash(rel) != hash_before:
                    changed = True
                self._relationships.append(rel)
                continue

            # If the item is not present in the previous list of relationship, we create a new one.
            self._relationships.append(
                await self.rel_class(schema=self.schema, branch=self.branch, at=self.at, node=self.node).new(
                    db=db, data=item
                )
            )
            changed = True

        # Check if some relationship got removed by checking if the previous list of relationship is a subset of the current list of not
        if set(previous_relationships.keys()) <= {rel.peer_id for rel in await self.get_relationships(db=db)}:
            changed = True

        if changed:
            self._relationships.validate()

        return changed

    async def add(self, data: dict[str, Any] | Node, db: InfrahubDatabase) -> bool:
        """Add a new relationship to the list of existing ones, avoid duplication."""
        if not isinstance(data, self.rel_class | dict) and not hasattr(data, "_schema"):
            raise ValidationError({self.name: f"Invalid data provided to form a relationship {data}"})

        await self._validate_hierarchy()

        previous_relationships = {rel.peer_id for rel in await self.get_relationships(db=db) if rel.peer_id}

        item_id = getattr(data, "id", None)
        if not item_id and isinstance(data, dict):
            item_id = data.get("id", None)

        if item_id in previous_relationships:
            return False

        # If the item ID is not present in the previous set of relationships, create a new one
        self._relationships.append(
            await self.rel_class(schema=self.schema, branch=self.branch, at=self.at, node=self.node).new(
                db=db, data=data
            )
        )

        return True

    async def resolve(self, db: InfrahubDatabase) -> None:
        for rel in self._relationships:
            await rel.resolve(db=db)

    async def remove_locally(
        self,
        peer_id: str | UUID,
        db: InfrahubDatabase,
    ) -> bool:
        """Remove a peer id from the local relationships list"""

        for idx, rel in enumerate(await self.get_relationships(db=db)):
            if str(rel.peer_id) != str(peer_id):
                continue

            self._relationships.pop(idx)
            return True

        raise IndexError("Relationship not found ... unexpected")

    async def remove_in_db(
        self,
        db: InfrahubDatabase,
        peer_data: RelationshipPeerData,
        at: Timestamp | None = None,
    ) -> None:
        remove_at = Timestamp(at)
        branch = self.get_branch_based_on_support_type()

        # - Update the existing relationship if we are on the same branch
        rel_ids_per_branch = peer_data.rel_ids_per_branch()

        # In which cases do we end up here and do not want to set `to` time?
        if branch.name in rel_ids_per_branch:
            await update_relationships_to([str(ri) for ri in rel_ids_per_branch[branch.name]], to=remove_at, db=db)

        # - Create a new rel of type DELETED if the existing relationship is on a different branch
        if peer_data.rels and {r.branch for r in peer_data.rels} == {peer_data.branch}:
            return

        query = await RelationshipDataDeleteQuery.init(
            db=db,
            rel=self.rel_class,
            schema=self.schema,
            source=self.node,
            data=peer_data,
            branch=branch,
            at=remove_at,
        )
        await query.execute(db=db)

    async def save(
        self, db: InfrahubDatabase, at: Timestamp | None = None
    ) -> RelationshipCardinalityManyChangelog | RelationshipCardinalityOneChangelog:
        """Create or Update the Relationship in the database."""

        await self.resolve(db=db)

        save_at = Timestamp(at)
        details = await self.fetch_relationship_ids(db=db, force_refresh=True)
        relationship_mapper = ChangelogRelationshipMapper(schema=self.schema)

        # If we have previously fetched the relationships from the database
        # Update the one in the database that shouldn't be here.
        if self.has_fetched_relationships:
            for peer_id in details.peer_ids_present_database_only:
                relationship_mapper.remove_peer(peer_data=details.peers_database[peer_id])
                await self.remove_in_db(peer_data=details.peers_database[peer_id], at=save_at, db=db)

        # Create the new relationship that are not present in the database
        #  and Compare the existing one
        for rel in await self.get_relationships(db=db):
            if rel.peer_id in details.peer_ids_present_local_only:
                await rel.save(at=save_at, db=db)

                relationship_mapper.add_peer_from_relationship(relationship=rel)

            elif rel.peer_id in details.peer_ids_present_both:
                if properties_not_matching := rel.compare_properties_with_data(
                    data=details.peers_database[rel.peer_id]
                ):
                    await rel.update(
                        at=save_at,
                        properties_to_update=properties_not_matching,
                        data=details.peers_database[rel.peer_id],
                        db=db,
                    )
                    relationship_mapper.add_updated_relationship(
                        relationship=rel,
                        old_data=details.peers_database[rel.peer_id],
                        properties_to_update=properties_not_matching,
                    )
            elif rel.schema.kind == RelationshipKind.PARENT:
                relationship_mapper.add_parent_from_relationship(relationship=rel)

        return relationship_mapper.changelog

    async def delete(
        self, db: InfrahubDatabase, at: Timestamp | None = None
    ) -> RelationshipCardinalityManyChangelog | RelationshipCardinalityOneChangelog:
        """Delete all the relationships."""

        delete_at = Timestamp(at)
        relationship_mapper = ChangelogRelationshipMapper(schema=self.schema)

        await self._fetch_relationships(at=delete_at, db=db, force_refresh=True)

        for rel in await self.get_relationships(db=db):
            relationship_mapper.delete_relationship(
                peer_kind=rel.get_peer_kind(), peer_id=rel.get_peer_id(), rel_schema=rel.schema
            )
            await rel.delete(at=delete_at, db=db)

        return relationship_mapper.changelog

    async def to_graphql(
        self, db: InfrahubDatabase, fields: dict | None = None, related_node_ids: set | None = None
    ) -> dict | None:
        # NOTE Need to investigate when and why we are passing the peer directly here, how do we account for many relationship
        if self.schema.cardinality == "many":
            raise TypeError("to_graphql is not available for relationship with multiple cardinality")

        relationships = await self.get_relationships(db=db)
        if not relationships:
            return None

        return await relationships[0].to_graphql(fields=fields, db=db, related_node_ids=related_node_ids)

    async def _validate_hierarchy(self) -> None:
        schema = self.node.get_schema()
        if schema.is_profile_schema or schema.is_template_schema or not schema.hierarchy:  # type: ignore[union-attr]
            return

        if self.name == "parent" and not schema.parent:  # type: ignore[union-attr]
            raise ValidationError({self.name: f"Not supported to assign a value to parent for {schema.kind}"})

        if self.name == "children" and not schema.children:  # type: ignore[union-attr]
            raise ValidationError({self.name: f"Not supported to assign some children for {schema.kind}"})
