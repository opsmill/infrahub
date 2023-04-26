from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_client.exceptions import Error, FilterNotFound
from infrahub_client.graphql import Mutation
from infrahub_client.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub_client.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_client.client import BaseClient, InfrahubClient, InfrahubClientSync


PROPERTIES_FLAG = ["is_visible", "is_protected"]
PROPERTIES_OBJECT = ["source", "owner"]


class Attribute:
    def __init__(self, name: str, schema: AttributeSchema, data: Union[Any, dict]):  # pylint: disable=unused-argument
        self.name = name

        if not isinstance(data, dict):
            data = {"value": data}

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        self._read_only = ["updated_at", "is_inherited"]

        self.id: Optional[str] = data.get("id", None)
        self.value: Optional[Any] = data.get("value", None)

        self.is_inherited: Optional[bool] = data.get("is_inherited", None)
        self.updated_at: Optional[str] = data.get("updated_at", None)

        self.is_visible: Optional[bool] = data.get("is_visible", None)
        self.is_protected: Optional[bool] = data.get("is_protected", None)

        self.source: Optional[NodeProperty] = None
        self.owner: Optional[NodeProperty] = None

        for prop_name in self._properties_object:
            if data.get(prop_name):
                setattr(self, prop_name, NodeProperty(data=data.get(prop_name)))

    def _generate_input_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {}

        if self.value is not None:
            data["value"] = self.value

        for prop_name in self._properties_flag:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)

        for prop_name in self._properties_object:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)._generate_input_data()

        return data

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"value": None}

        for prop_name in self._properties_flag:
            data[prop_name] = None
        for prop_name in self._properties_object:
            data[prop_name] = {"id": None, "display_label": None, "__typename": None}

        return data


class RelatedNodeBase:
    def __init__(
        self, client: BaseClient, schema: RelationshipSchema, data: Union[Any, dict], name: Optional[str] = None
    ):
        self.schema = schema
        self.name = name

        self._client = client

        self._properties_flag = PROPERTIES_FLAG
        self._properties_object = PROPERTIES_OBJECT
        self._properties = self._properties_flag + self._properties_object

        self._peer: Optional[InfrahubNode] = None
        self._id: Optional[str] = None
        self._display_label: Optional[str] = None
        self._typename: Optional[str] = None

        if isinstance(data, InfrahubNode):
            self._peer = data
        elif not isinstance(data, dict):
            data = {"id": data}

        if isinstance(data, dict):
            self._id: Optional[str] = data.get("id", None)
            self._display_label = data.get("display_label", None)
            self._typename = data.get("__typename", None)
            self.updated_at: Optional[bool] = data.get("_relation__updated_at", None)

        for prop in self._properties:
            if value := data.get(prop, None):
                setattr(self, prop, value)
                continue

            setattr(self, prop, data.get(f"_relation__{prop}", None))

    @property
    def id(self):
        if self._peer:
            return self._peer.id
        return self._id

    @property
    def display_label(self):
        if self._peer:
            return self._peer.display_label
        return self._display_label

    @property
    def typename(self):
        if self._peer:
            return self._peer.typename
        return self.typename

    def _generate_input_data(self) -> Dict[str, Any]:
        data = {}

        if self.id is not None:
            data["id"] = self.id

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[f"_relation__{prop_name}"] = getattr(self, prop_name)

        return data

    def _get(self) -> InfrahubNodeBase:
        if self._peer:
            return self._peer

        if self.id and self.typename and self._client.internal_store:
            self._client.store.get(key=self.id, kind=self.typename)


class RelatedNode(RelatedNodeBase):
    async def fetch(self):
        if not self.id or not self.typename:
            raise Error("Unable to fetch the peer, id and/or typename are not defined")

        self._peer = await self._client.get(ids=[self], kind=self.typename)

    @property
    def peer(self) -> InfrahubNode:
        return self.get()

    def get(self) -> InfrahubNode:
        return self._get()


class RelatedNodeSync(RelatedNodeBase):
    @property
    def peer(self) -> InfrahubNodeSync:
        return self.get()

    def get(self) -> InfrahubNodeSync:
        return self._get()


class RelationshipManagerBase:
    _related_node_class = RelatedNodeBase

    def __init__(self, name: str, client: BaseClient, schema: RelationshipSchema, data: Union[Any, dict]):
        self.name = name
        self.schema = schema
        self.client = client
        self.peers: List[RelatedNodeBase] = []

        self._properties_flag = PROPERTIES_FLAG
        self._properties_object = PROPERTIES_OBJECT
        self._properties = self._properties_flag + self._properties_object

        if data is None:
            return

        if not isinstance(data, list):
            raise ValueError(f"{name} found a {type(data)} instead of a list")

        for item in data:
            self.peers.append(self._related_node_class(name=name, client=client, schema=schema, data=item))

    def add(self, data: Union[str, RelatedNodeBase, dict]) -> None:
        """Add a new peer to this relationship.
        Need to check if the peer is already present
        """

        # TODO add some check to ensure
        # that we are not adding a node that already exist
        self.peers.append(self._related_node_class(schema=self.schema, data=data))

    def remove(self, data: Any) -> None:
        pass

    def _generate_input_data(self) -> List[Dict]:
        return [peer._generate_input_data() for peer in self.peers]

    @classmethod
    def _generate_query_data(cls) -> Dict:
        data: Dict[str, Any] = {"id": None, "display_label": None, "__typename": None}

        for prop_name in PROPERTIES_FLAG:
            data[f"_relation__{prop_name}"] = None
        for prop_name in PROPERTIES_OBJECT:
            data[f"_relation__{prop_name}"] = {"id": None, "display_label": None, "__typename": None}

        return data


class RelationshipManager(RelationshipManagerBase):
    _related_node_class = RelatedNode

    def __init__(self, name: str, client: InfrahubClient, schema: RelationshipSchema, data: Union[Any, dict]):
        super().__init__(name=name, client=client, schema=schema, data=data)

    async def fetch(self) -> None:
        for peer in self.peers:
            await peer.fetch()


class RelationshipManagerSync(RelationshipManagerBase):
    _related_node_class = RelatedNodeSync

    def __init__(self, name: str, client: InfrahubClientSync, schema: RelationshipSchema, data: Union[Any, dict]):
        super().__init__(name=name, client=client, schema=schema, data=data)

    async def fetch(self) -> None:
        for peer in self.peers:
            peer.fetch()


class InfrahubNodeBase:
    _attribute_class = Attribute
    _related_node_class = RelatedNodeBase
    _relationship_manager_class = RelationshipManagerBase

    def __init__(
        self, client: BaseClient, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        self._schema = schema
        self._data = data
        self._client = client
        self._branch = branch or self._client.default_branch

        self.id: Optional[str] = data.get("id", None) if isinstance(data, dict) else None
        self.display_label: Optional[str] = data.get("display_label", None) if isinstance(data, dict) else None
        self.typename: Optional[str] = data.get("__typename", schema.kind) if isinstance(data, dict) else schema.kind

        self._attributes = [item.name for item in self._schema.attributes]
        self._relationships = [item.name for item in self._schema.relationships]

        for attr_name in self._attributes:
            attr_schema = [attr for attr in self._schema.attributes if attr.name == attr_name][0]
            attr_data = data.get(attr_name, None) if isinstance(data, dict) else None
            setattr(self, attr_name, Attribute(name=attr_name, schema=attr_schema, data=attr_data))

        for rel_name in self._relationships:
            rel_schema = [rel for rel in self._schema.relationships if rel.name == rel_name][0]
            rel_data = data.get(rel_name, None) if isinstance(data, dict) else None

            if rel_schema.cardinality == "one":
                setattr(self, f"_{rel_name}", None)
                setattr(
                    self.__class__,
                    rel_name,
                    generate_relationship_property(
                        name=rel_name, client=self._client, node_class=self._related_node_class
                    ),
                )
                setattr(self, rel_name, rel_data)
            else:
                setattr(
                    self,
                    rel_name,
                    self._relationship_manager_class(
                        name=rel_name, client=self._client, schema=rel_schema, data=rel_data
                    ),
                )

    def __repr__(self) -> str:
        if self.display_label:
            return self.display_label
        if not self.id:
            return f"{self._schema.kind} (no id yet)"

        return f"{self._schema.kind} ({self.id})"

    def _generate_input_data(self) -> Dict[str, Dict]:
        """Generate a dictionnary that represent the input data required by a mutation.

        Returns:
            Dict[str, Dict]: Representation of an input data in dict format
        """
        data = {}
        for item_name in self._attributes + self._relationships:
            item = getattr(self, item_name)
            if item is None:
                continue

            item_data = item._generate_input_data()
            if item_data:
                data[item_name] = item_data

        return {"data": data}

    def generate_query_data(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Union[Any, Dict]]:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        if filters:
            data["@filters"] = filters

        for attr_name in self._attributes:
            attr: Attribute = getattr(self, attr_name)
            attr_data = attr._generate_query_data()
            if attr_data:
                data[attr_name] = attr_data

        for rel_name in self._relationships:
            rel_data = RelationshipManager._generate_query_data()
            data[rel_name] = rel_data

        return {self._schema.name: data}

    def validate_filters(self, filters: Optional[Dict[str, Any]] = None) -> bool:
        if not filters:
            return True

        for filter_name in filters.keys():
            found = False
            for filter_schema in self._schema.filters:
                if filter_name == filter_schema.name:
                    found = True
                    break
            if not found:
                valid_filters = [entry.name for entry in self._schema.filters]
                raise FilterNotFound(identifier=filter_name, kind=self._schema.kind, filters=valid_filters)

        return True


class InfrahubNode(InfrahubNodeBase):
    _related_node_class = RelatedNode
    _relationship_manager_class = RelationshipManager

    def __init__(
        self, client: InfrahubClient, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        super().__init__(client=client, schema=schema, branch=branch, data=data)

    async def delete(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        input_data = {"data": {"id": self.id}}
        mutation_query = {"ok": None}
        query = Mutation(mutation=f"{self._schema.name}_delete", input_data=input_data, query=mutation_query)
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-delete",
        )

    async def save(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        if not self.id:
            await self._create(at=at)
        else:
            await self._update(at=at)

        if self._client.internal_store and self.id:
            self._client.store.set(key=self.id, node=self)

    async def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.name}_create"
        query = Mutation(mutation=mutation_name, input_data=input_data, query=mutation_query)

        response = await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
        )
        self.id = response[mutation_name]["object"]["id"]

    async def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(mutation=f"{self._schema.name}_update", input_data=input_data, query=mutation_query)
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-update",
        )


class InfrahubNodeSync(InfrahubNodeBase):
    _related_node_class = RelatedNodeSync
    _relationship_manager_class = RelationshipManagerSync

    def __init__(
        self, client: InfrahubClientSync, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        super().__init__(client=client, schema=schema, branch=branch, data=data)

    def delete(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        input_data = {"data": {"id": self.id}}
        mutation_query = {"ok": None}
        query = Mutation(mutation=f"{self._schema.name}_delete", input_data=input_data, query=mutation_query)
        self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-delete",
        )

    def save(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        if not self.id:
            self._create(at=at)
        else:
            self._update(at=at)

    def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.name}_create"
        query = Mutation(mutation=mutation_name, input_data=input_data, query=mutation_query)

        response = self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
        )
        self.id = response[mutation_name]["object"]["id"]

    def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(mutation=f"{self._schema.name}_update", input_data=input_data, query=mutation_query)
        self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-update",
        )


class NodeProperty:
    def __init__(self, data: Union[dict, str]):
        self.id = None
        self.display_label = None
        self.typename = None

        if isinstance(data, str):
            self.id = data
        elif isinstance(data, dict):
            self.id = data.get("id", None)
            self.display_label = data.get("display_label", None)
            self.typename = data.get("__typename", None)

    def _generate_input_data(self) -> Union[str, None]:
        return self.id


def generate_relationship_property(client: BaseClient, name: str, node_class: type(RelatedNodeBase)):  # type: ignore
    """Return a property that stores values under a private non-public name."""
    internal_name = "_" + name.lower()
    external_name = name

    @property  # type: ignore
    def prop(self):  # type: ignore
        return getattr(self, internal_name)

    @prop.setter
    def prop(self, value):  # type: ignore
        if isinstance(value, RelatedNode) or value is None:
            setattr(self, internal_name, value)
        else:
            schema = [rel for rel in self._schema.relationships if rel.name == external_name][0]
            setattr(self, internal_name, RelatedNode(name=external_name, client=client, schema=schema, data=value))

    return prop
