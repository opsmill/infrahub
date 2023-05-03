from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_client.exceptions import Error, FilterNotFound, NodeNotFound
from infrahub_client.graphql import Mutation
from infrahub_client.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub_client.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_client.client import InfrahubClient, InfrahubClientSync


PROPERTIES_FLAG = ["is_visible", "is_protected"]
PROPERTIES_OBJECT = ["source", "owner"]
SAFE_VALUE = re.compile(r"(^[\. a-zA-Z0-9_-]+$)|(^$)")


class Attribute:
    def __init__(self, name: str, schema: AttributeSchema, data: Union[Any, dict]):
        self.name = name
        self._schema = schema

        if not isinstance(data, dict):
            data = {"value": data}

        self._properties_flag = PROPERTIES_FLAG
        self._properties_object = PROPERTIES_OBJECT
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
        variables: Dict[str, Any] = {}

        if self.value is None:
            return data

        if isinstance(self.value, str):
            if SAFE_VALUE.match(self.value):
                data["value"] = self.value
            else:
                var_name = f"value_{uuid.uuid4().hex}"
                variables[var_name] = self.value
                data["value"] = f"${var_name}"
        else:
            data["value"] = self.value

        for prop_name in self._properties_flag:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)

        for prop_name in self._properties_object:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)._generate_input_data()

        return {"data": data, "variables": variables}

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"value": None}

        for prop_name in self._properties_flag:
            data[prop_name] = None
        for prop_name in self._properties_object:
            data[prop_name] = {"id": None, "display_label": None, "__typename": None}

        return data


class RelatedNodeBase:
    def __init__(
        self,
        branch: str,
        schema: RelationshipSchema,
        data: Union[Any, dict],
        name: Optional[str] = None,
    ):
        self.schema = schema
        self.name = name

        self._branch = branch

        self._properties_flag = PROPERTIES_FLAG
        self._properties_object = PROPERTIES_OBJECT
        self._properties = self._properties_flag + self._properties_object

        self._peer = None
        self._id: Optional[str] = None
        self._display_label: Optional[str] = None
        self._typename: Optional[str] = None

        if isinstance(data, (InfrahubNode, InfrahubNodeSync)):
            self._peer = data

            for prop in self._properties:
                setattr(self, prop, None)

        elif not isinstance(data, dict):
            data = {"id": data}

        if isinstance(data, dict):
            self._id = data.get("id", None)
            self._display_label = data.get("display_label", None)
            self._typename = data.get("__typename", None)
            self.updated_at: Optional[bool] = data.get("_relation__updated_at", None)

            if self._typename and self._typename.startswith("Related"):
                self._typename = self._typename[7:]

            for prop in self._properties:
                if value := data.get(prop, None):
                    setattr(self, prop, value)
                    continue

                prop_data = data.get(f"_relation__{prop}", None)
                if prop_data and isinstance(prop_data, dict) and "id" in prop_data:
                    setattr(self, prop, prop_data["id"])
                elif prop_data and isinstance(prop_data, (str, bool)):
                    setattr(self, prop, prop_data)
                else:
                    setattr(self, prop, None)

    @property
    def id(self) -> Optional[str]:
        if self._peer:
            return self._peer.id
        return self._id

    @property
    def display_label(self) -> Optional[str]:
        if self._peer:
            return self._peer.display_label
        return self._display_label

    @property
    def typename(self) -> Optional[str]:
        if self._peer:
            return self._peer.typename
        return self._typename

    def _generate_input_data(self) -> Dict[str, Any]:
        data = {}

        if self.id is not None:
            data["id"] = self.id

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[f"_relation__{prop_name}"] = getattr(self, prop_name)

        return data


class RelatedNode(RelatedNodeBase):
    def __init__(
        self,
        client: InfrahubClient,
        branch: str,
        schema: RelationshipSchema,
        data: Union[Any, dict],
        name: Optional[str] = None,
    ):
        self._client = client
        super().__init__(branch=branch, schema=schema, data=data, name=name)

    async def fetch(self) -> None:
        if not self.id or not self.typename:
            raise Error("Unable to fetch the peer, id and/or typename are not defined")

        self._peer = await self._client.get(ids=[self.id], kind=self.typename, populate_store=True)

    @property
    def peer(self) -> InfrahubNode:
        return self.get()

    def get(self) -> InfrahubNode:
        if self._peer:
            return self._peer  # type: ignore[return-value]

        if not self.id:
            raise ValueError("Node id but be defined to query it.")

        if self.id and self.typename:
            return self._client.store.get(key=self.id, kind=self.typename)  # type: ignore[return-value]

        raise NodeNotFound(branch_name=self._branch, node_type=self.schema.peer, identifier={"key": [self.id]})


class RelatedNodeSync(RelatedNodeBase):
    def __init__(
        self,
        client: InfrahubClientSync,
        branch: str,
        schema: RelationshipSchema,
        data: Union[Any, dict],
        name: Optional[str] = None,
    ):
        self._client = client
        super().__init__(branch=branch, schema=schema, data=data, name=name)

    def fetch(self) -> None:
        if not self.id or not self.typename:
            raise Error("Unable to fetch the peer, id and/or typename are not defined")

        self._peer = self._client.get(ids=[self.id], kind=self.typename, populate_store=True)

    @property
    def peer(self) -> InfrahubNodeSync:
        return self.get()

    def get(self) -> InfrahubNodeSync:
        if self._peer:
            return self._peer  # type: ignore[return-value]

        if not self.id:
            raise ValueError("Node id but be defined to query it.")

        if self.id and self.typename:
            return self._client.store.get(key=self.id, kind=self.typename)  # type: ignore[return-value]

        raise NodeNotFound(branch_name=self._branch, node_type=self.schema.peer, identifier={"key": [self.id]})


class RelationshipManagerBase:
    def __init__(self, name: str, branch: str, schema: RelationshipSchema):
        self.name = name
        self.schema = schema
        self.branch = branch

        self._properties_flag = PROPERTIES_FLAG
        self._properties_object = PROPERTIES_OBJECT
        self._properties = self._properties_flag + self._properties_object

        self.peers: List[Union[RelatedNode, RelatedNodeSync]] = []

    @property
    def peer_ids(self) -> List[str]:
        return [peer.id for peer in self.peers if peer.id]

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
    def __init__(
        self, name: str, client: InfrahubClient, branch: str, schema: RelationshipSchema, data: Union[Any, dict]
    ):
        self.client = client

        super().__init__(name=name, schema=schema, branch=branch)

        if data is None:
            return

        if not isinstance(data, list):
            raise ValueError(f"{name} found a {type(data)} instead of a list")

        for item in data:
            self.peers.append(RelatedNode(name=name, client=self.client, branch=self.branch, schema=schema, data=item))

    def __getitem__(self, item: int) -> RelatedNode:
        return self.peers[item]  # type: ignore[return-value]

    async def fetch(self) -> None:
        for peer in self.peers:
            await peer.fetch()  # type: ignore[misc]

    def add(self, data: Union[str, RelatedNode, dict]) -> None:
        """Add a new peer to this relationship."""
        new_node = RelatedNode(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if new_node.id and new_node.id not in self.peer_ids:
            self.peers.append(RelatedNode(schema=self.schema, client=self.client, branch=self.branch, data=data))

    def remove(self, data: Union[str, RelatedNode, dict]) -> None:
        node_to_remove = RelatedNode(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if node_to_remove.id and node_to_remove.id in self.peer_ids:
            idx = self.peer_ids.index(node_to_remove.id)
            if self.peers[idx].id != node_to_remove.id:
                raise IndexError(f"Unexpected situation, the node with the index {idx} should be {node_to_remove.id}")

            self.peers.pop(idx)


class RelationshipManagerSync(RelationshipManagerBase):
    def __init__(
        self, name: str, client: InfrahubClientSync, branch: str, schema: RelationshipSchema, data: Union[Any, dict]
    ):
        self.client = client

        super().__init__(name=name, schema=schema, branch=branch)

        if data is None:
            return

        if not isinstance(data, list):
            raise ValueError(f"{name} found a {type(data)} instead of a list")

        for item in data:
            self.peers.append(
                RelatedNodeSync(name=name, client=self.client, branch=self.branch, schema=schema, data=item)
            )

    def __getitem__(self, item: int) -> RelatedNodeSync:
        return self.peers[item]  # type: ignore[return-value]

    def fetch(self) -> None:
        for peer in self.peers:
            peer.fetch()

    def add(self, data: Union[str, RelatedNodeSync, dict]) -> None:
        """Add a new peer to this relationship."""
        new_node = RelatedNodeSync(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if new_node.id and new_node.id not in self.peer_ids:
            self.peers.append(RelatedNodeSync(schema=self.schema, client=self.client, branch=self.branch, data=data))

    def remove(self, data: Union[str, RelatedNodeSync, dict]) -> None:
        node_to_remove = RelatedNodeSync(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if node_to_remove.id and node_to_remove.id in self.peer_ids:
            idx = self.peer_ids.index(node_to_remove.id)
            if self.peers[idx].id != node_to_remove.id:
                raise IndexError(f"Unexpected situation, the node with the index {idx} should be {node_to_remove.id}")

            self.peers.pop(idx)


class InfrahubNodeBase:
    def __init__(self, schema: NodeSchema, branch: str, data: Optional[dict] = None) -> None:
        self._schema = schema
        self._data = data
        self._branch = branch

        self.id: Optional[str] = data.get("id", None) if isinstance(data, dict) else None
        self.display_label: Optional[str] = data.get("display_label", None) if isinstance(data, dict) else None
        self.typename: Optional[str] = data.get("__typename", schema.kind) if isinstance(data, dict) else schema.kind

        self._attributes = [item.name for item in self._schema.attributes]
        self._relationships = [item.name for item in self._schema.relationships]

        self._init_attributes(data)
        self._init_relationships(data)

    def _init_attributes(self, data: Optional[dict] = None) -> None:
        for attr_name in self._attributes:
            attr_schema = [attr for attr in self._schema.attributes if attr.name == attr_name][0]
            attr_data = data.get(attr_name, None) if isinstance(data, dict) else None
            setattr(self, attr_name, Attribute(name=attr_name, schema=attr_schema, data=attr_data))

    def _init_relationships(self, data: Optional[dict] = None) -> None:
        pass

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
        variables = {}
        for item_name in self._attributes + self._relationships:
            item = getattr(self, item_name)
            # BLOCKED by https://github.com/opsmill/infrahub/issues/330
            # if (
            #     item is None
            #     and item_name in self._relationships
            #     and self._schema.get_relationship(item_name).cardinality == "one"
            # ):
            #     data[item_name] = None
            #     continue
            # el
            if item is None:
                continue

            item_data = item._generate_input_data()
            rel_schema = self._schema.get_relationship(name=item_name, raise_on_error=False)

            if item_data and isinstance(item_data, dict):
                if variable_values := item_data.get("data"):
                    data[item_name] = variable_values
                else:
                    data[item_name] = item_data
                if variable_names := item_data.get("variables"):
                    for key, value in variable_names.items():
                        variables[key] = value
            elif item_data and isinstance(item_data, list):
                data[item_name] = item_data
            elif item_name in self._relationships and rel_schema:
                if rel_schema.cardinality == "many":
                    data[item_name] = []

        mutation_variables = {key: type(value) for key, value in variables.items()}

        return {"data": {"data": data}, "variables": variables, "mutation_variables": mutation_variables}

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
    def __init__(
        self, client: InfrahubClient, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        self._client = client
        super().__init__(schema=schema, branch=branch or client.default_branch, data=data)

    def _init_relationships(self, data: Optional[dict] = None) -> None:
        for rel_name in self._relationships:
            rel_schema = [rel for rel in self._schema.relationships if rel.name == rel_name][0]
            rel_data = data.get(rel_name, None) if isinstance(data, dict) else None

            if rel_schema.cardinality == "one":
                setattr(self, f"_{rel_name}", None)
                setattr(
                    self.__class__,
                    rel_name,
                    generate_relationship_property(name=rel_name, node=self, node_class=RelatedNode),  # type: ignore[arg-type]
                )
                setattr(self, rel_name, rel_data)
            else:
                setattr(
                    self,
                    rel_name,
                    RelationshipManager(
                        name=rel_name, client=self._client, branch=self._branch, schema=rel_schema, data=rel_data
                    ),
                )

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

        if self.id:
            self._client.store.set(key=self.id, node=self)

    async def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.name}_create"
        query = Mutation(
            mutation=mutation_name,
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )
        response = await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
            variables=input_data["variables"],
        )
        self.id = response[mutation_name]["object"]["id"]

    async def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(
            mutation=f"{self._schema.name}_update",
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-update",
            variables=input_data["variables"],
        )


class InfrahubNodeSync(InfrahubNodeBase):
    def __init__(
        self, client: InfrahubClientSync, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        self._client = client
        super().__init__(schema=schema, branch=branch or client.default_branch, data=data)

    def _init_relationships(self, data: Optional[dict] = None) -> None:
        for rel_name in self._relationships:
            rel_schema = [rel for rel in self._schema.relationships if rel.name == rel_name][0]
            rel_data = data.get(rel_name, None) if isinstance(data, dict) else None

            if rel_schema.cardinality == "one":
                setattr(self, f"_{rel_name}", None)
                setattr(
                    self.__class__,
                    rel_name,
                    generate_relationship_property(name=rel_name, node=self, node_class=RelatedNodeSync),  # type: ignore[arg-type]
                )
                setattr(self, rel_name, rel_data)
            else:
                setattr(
                    self,
                    rel_name,
                    RelationshipManagerSync(
                        name=rel_name, client=self._client, branch=self._branch, schema=rel_schema, data=rel_data
                    ),
                )

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
        query = Mutation(
            mutation=mutation_name,
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )

        response = self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
            variables=input_data["variables"],
        )
        self.id = response[mutation_name]["object"]["id"]

    def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(
            mutation=f"{self._schema.name}_update",
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )

        self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-update",
            variables=input_data["variables"],
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


def generate_relationship_property(node: Union[InfrahubNode, InfrahubNodeSync], name: str, node_class):  # type: ignore
    """Return a property that stores values under a private non-public name."""
    internal_name = "_" + name.lower()
    external_name = name

    @property  # type: ignore
    def prop(self):  # type: ignore
        return getattr(self, internal_name)

    @prop.setter
    def prop(self, value):  # type: ignore
        if isinstance(value, RelatedNodeBase) or value is None:
            setattr(self, internal_name, value)
        else:
            schema = [rel for rel in self._schema.relationships if rel.name == external_name][0]
            setattr(
                self,
                internal_name,
                node_class(name=external_name, branch=node._branch, client=node._client, schema=schema, data=value),
            )

    return prop
