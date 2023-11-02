from __future__ import annotations

import ipaddress
import re
from copy import copy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    get_args,
)

from infrahub_sdk.exceptions import Error, FilterNotFound, NodeNotFound
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.schema import GenericSchema, RelationshipCardinality, RelationshipKind
from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.utils import compare_lists, get_flat_value
from infrahub_sdk.uuidt import UUIDT

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync
    from infrahub_sdk.schema import AttributeSchema, NodeSchema, RelationshipSchema

# pylint: disable=too-many-lines

PROPERTIES_FLAG = ["is_visible", "is_protected"]
PROPERTIES_OBJECT = ["source", "owner"]
SAFE_VALUE = re.compile(r"(^[\. /:a-zA-Z0-9_-]+$)|(^$)")

IP_TYPES = Union[
    ipaddress.IPv4Interface,
    ipaddress.IPv6Interface,
    ipaddress.IPv4Network,
    ipaddress.IPv6Network,
]


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

        if self.value:
            value_mapper: Dict[str, Callable] = {
                "IPHost": ipaddress.ip_interface,
                "IPNetwork": ipaddress.ip_network,
            }
            mapper = value_mapper.get(schema.kind, lambda value: value)
            self.value = mapper(data.get("value"))

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
                var_name = f"value_{UUIDT.new().hex}"
                variables[var_name] = self.value
                data["value"] = f"${var_name}"
        elif isinstance(self.value, get_args(IP_TYPES)):
            data["value"] = self.value.with_prefixlen
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
            # To support both with and without pagination, we split data into node_data and properties_data
            # We should probably clean that once we'll remove the code without pagination.
            node_data = data.get("node", data)
            properties_data = data.get("properties", data)

            if node_data:
                self._id = node_data.get("id", None)
                self._display_label = node_data.get("display_label", None)
                self._typename = node_data.get("__typename", None)

            self.updated_at: Optional[str] = data.get("updated_at", data.get("_relation__updated_at", None))

            # FIXME, we won't need that once we are only supporting paginated results
            if self._typename and self._typename.startswith("Related"):
                self._typename = self._typename[7:]

            for prop in self._properties:
                prop_data = properties_data.get(prop, properties_data.get(f"_relation__{prop}", None))
                if prop_data and isinstance(prop_data, dict) and "id" in prop_data:
                    setattr(self, prop, prop_data["id"])
                elif prop_data and isinstance(prop_data, (str, bool)):
                    setattr(self, prop, prop_data)
                else:
                    setattr(self, prop, None)

    @property
    def initialized(self) -> bool:
        if self.id:
            return True
        return False

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

    @classmethod
    def _generate_query_data(cls) -> Dict:
        data: Dict[str, Any] = {"node": {"id": None, "display_label": None, "__typename": None}}

        properties: Dict[str, Any] = {}
        for prop_name in PROPERTIES_FLAG:
            properties[prop_name] = None
        for prop_name in PROPERTIES_OBJECT:
            properties[prop_name] = {
                "id": None,
                "display_label": None,
                "__typename": None,
            }

        if properties:
            data["properties"] = properties
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

        raise NodeNotFound(
            branch_name=self._branch,
            node_type=self.schema.peer,
            identifier={"key": [self.id]},
        )


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

        raise NodeNotFound(
            branch_name=self._branch,
            node_type=self.schema.peer,
            identifier={"key": [self.id]},
        )


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
        data: Dict[str, Any] = {
            "count": None,
            "edges": {"node": {"id": None, "display_label": None, "__typename": None}},
        }

        properties: Dict[str, Any] = {}
        for prop_name in PROPERTIES_FLAG:
            properties[prop_name] = None
        for prop_name in PROPERTIES_OBJECT:
            properties[prop_name] = {
                "id": None,
                "display_label": None,
                "__typename": None,
            }

        if properties:
            data["edges"]["properties"] = properties
        return data


class RelationshipManager(RelationshipManagerBase):
    def __init__(
        self,
        name: str,
        client: InfrahubClient,
        node: InfrahubNode,
        branch: str,
        schema: RelationshipSchema,
        data: Union[Any, dict],
    ):
        self.client = client
        self.node = node

        self.initialized = data is not None

        super().__init__(name=name, schema=schema, branch=branch)

        if data is None:
            return

        if isinstance(data, list):
            for item in data:
                self.peers.append(
                    RelatedNode(
                        name=name,
                        client=self.client,
                        branch=self.branch,
                        schema=schema,
                        data=item,
                    )
                )

        elif isinstance(data, dict) and "edges" in data:
            for item in data["edges"]:
                self.peers.append(
                    RelatedNode(
                        name=name,
                        client=self.client,
                        branch=self.branch,
                        schema=schema,
                        data=item,
                    )
                )

        else:
            raise ValueError(f"Unexpected format for {name} found a {type(data)}, {data}")

    def __getitem__(self, item: int) -> RelatedNode:
        return self.peers[item]  # type: ignore[return-value]

    async def fetch(self) -> None:
        if not self.initialized:
            exclude = self.node._schema.relationship_names + self.node._schema.attribute_names
            exclude.remove(self.schema.name)
            node = await self.client.get(
                kind=self.node._schema.kind,
                id=self.node.id,
                include=[self.schema.name],
                exclude=exclude,
            )
            rm = getattr(node, self.schema.name)
            self.peers = rm.peers
            self.initialized = True

        for peer in self.peers:
            await peer.fetch()  # type: ignore[misc]

    def add(self, data: Union[str, RelatedNode, dict]) -> None:
        """Add a new peer to this relationship."""
        new_node = RelatedNode(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if new_node.id and new_node.id not in self.peer_ids:
            self.peers.append(
                RelatedNode(
                    schema=self.schema,
                    client=self.client,
                    branch=self.branch,
                    data=data,
                )
            )

    def remove(self, data: Union[str, RelatedNode, dict]) -> None:
        node_to_remove = RelatedNode(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if node_to_remove.id and node_to_remove.id in self.peer_ids:
            idx = self.peer_ids.index(node_to_remove.id)
            if self.peers[idx].id != node_to_remove.id:
                raise IndexError(f"Unexpected situation, the node with the index {idx} should be {node_to_remove.id}")

            self.peers.pop(idx)


class RelationshipManagerSync(RelationshipManagerBase):
    def __init__(
        self,
        name: str,
        client: InfrahubClientSync,
        node: InfrahubNodeSync,
        branch: str,
        schema: RelationshipSchema,
        data: Union[Any, dict],
    ):
        self.client = client
        self.node = node

        self.initialized = data is not None

        super().__init__(name=name, schema=schema, branch=branch)

        if data is None:
            return

        if isinstance(data, list):
            for item in data:
                self.peers.append(
                    RelatedNodeSync(
                        name=name,
                        client=self.client,
                        branch=self.branch,
                        schema=schema,
                        data=item,
                    )
                )

        elif isinstance(data, dict) and "edges" in data:
            for item in data["edges"]:
                self.peers.append(
                    RelatedNodeSync(
                        name=name,
                        client=self.client,
                        branch=self.branch,
                        schema=schema,
                        data=item,
                    )
                )

        else:
            raise ValueError(f"Unexpected format for {name} found a {type(data)}, {data}")

    def __getitem__(self, item: int) -> RelatedNodeSync:
        return self.peers[item]  # type: ignore[return-value]

    def fetch(self) -> None:
        if not self.initialized:
            exclude = self.node._schema.relationship_names + self.node._schema.attribute_names
            exclude.remove(self.schema.name)
            node = self.client.get(
                kind=self.node._schema.kind,
                id=self.node.id,
                include=[self.schema.name],
                exclude=exclude,
            )
            rm = getattr(node, self.schema.name)
            self.peers = rm.peers
            self.initialized = True

        for peer in self.peers:
            peer.fetch()

    def add(self, data: Union[str, RelatedNodeSync, dict]) -> None:
        """Add a new peer to this relationship."""
        new_node = RelatedNodeSync(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if new_node.id and new_node.id not in self.peer_ids:
            self.peers.append(
                RelatedNodeSync(
                    schema=self.schema,
                    client=self.client,
                    branch=self.branch,
                    data=data,
                )
            )

    def remove(self, data: Union[str, RelatedNodeSync, dict]) -> None:
        node_to_remove = RelatedNodeSync(schema=self.schema, client=self.client, branch=self.branch, data=data)

        if node_to_remove.id and node_to_remove.id in self.peer_ids:
            idx = self.peer_ids.index(node_to_remove.id)
            if self.peers[idx].id != node_to_remove.id:
                raise IndexError(f"Unexpected situation, the node with the index {idx} should be {node_to_remove.id}")

            self.peers.pop(idx)


class InfrahubNodeBase:
    def __init__(
        self,
        schema: Union[NodeSchema, GenericSchema],
        branch: str,
        data: Optional[dict] = None,
    ) -> None:
        self._schema = schema
        self._data = data
        self._branch = branch
        self._existing: bool = True

        extracted_uuid = data.get("id", None) if isinstance(data, dict) else None
        self.id = extracted_uuid or str(UUIDT())
        self.display_label: Optional[str] = data.get("display_label", None) if isinstance(data, dict) else None
        self.typename: Optional[str] = data.get("__typename", schema.kind) if isinstance(data, dict) else schema.kind

        self._attributes = [item.name for item in self._schema.attributes]
        self._relationships = [item.name for item in self._schema.relationships]

        if not extracted_uuid:
            self._existing = False

        self._init_attributes(data)
        self._init_relationships(data)

    def _init_attributes(self, data: Optional[dict] = None) -> None:
        for attr_name in self._attributes:
            attr_schema = [attr for attr in self._schema.attributes if attr.name == attr_name][0]
            attr_data = data.get(attr_name, None) if isinstance(data, dict) else None
            setattr(
                self,
                attr_name,
                Attribute(name=attr_name, schema=attr_schema, data=attr_data),
            )

    def _init_relationships(self, data: Optional[dict] = None) -> None:
        pass

    def __repr__(self) -> str:
        if self.display_label:
            return self.display_label
        if not self._existing:
            return f"{self._schema.kind} ({self.id})[NEW]"

        return f"{self._schema.kind} ({self.id}) "

    def _generate_input_data(self, update: bool = False) -> Dict[str, Dict]:
        """Generate a dictionnary that represent the input data required by a mutation.

        Returns:
            Dict[str, Dict]: Representation of an input data in dict format
        """
        # pylint: disable=too-many-branches
        data = {}
        variables = {}
        for item_name in self._attributes:
            attr: Attribute = getattr(self, item_name)
            attr_data = attr._generate_input_data()

            # NOTE, this code has been inherited when we splitted attributes and relationships
            # into 2 loops, most likely it's possible to simply it
            if attr_data and isinstance(attr_data, dict):
                if variable_values := attr_data.get("data"):
                    data[item_name] = variable_values
                else:
                    data[item_name] = attr_data
                if variable_names := attr_data.get("variables"):
                    variables.update(variable_names)

            elif attr_data and isinstance(attr_data, list):
                data[item_name] = attr_data

        for item_name in self._relationships:
            rel_schema = self._schema.get_relationship(name=item_name)
            if not rel_schema:
                continue
            if rel_schema.kind in [RelationshipKind.GROUP, RelationshipKind.COMPONENT]:
                continue

            rel: Union[RelatedNodeBase, RelationshipManagerBase] = getattr(self, item_name)

            # BLOCKED by https://github.com/opsmill/infrahub/issues/330
            # if (
            #     item is None
            #     and item_name in self._relationships
            #     and self._schema.get_relationship(item_name).cardinality == "one"
            # ):
            #     data[item_name] = None
            #     continue
            # el
            if rel is None:
                continue

            rel_data = rel._generate_input_data()

            if rel_data and isinstance(rel_data, dict):
                if variable_values := rel_data.get("data"):
                    data[item_name] = variable_values
                else:
                    data[item_name] = rel_data
                if variable_names := rel_data.get("variables"):
                    variables.update(variable_names)

            elif rel_data and isinstance(rel_data, list):
                data[item_name] = rel_data
            elif rel_schema.cardinality == RelationshipCardinality.MANY:
                data[item_name] = []

        if update:
            data, variables = self._strip_unmodified(data=data, variables=variables)

        mutation_variables = {key: type(value) for key, value in variables.items()}

        return {
            "data": {"data": data},
            "variables": variables,
            "mutation_variables": mutation_variables,
        }

    @staticmethod
    def _strip_unmodified_dict(data: dict, original_data: dict, variables: dict, item: str) -> None:
        for item_key in original_data[item].keys():
            if isinstance(data[item], dict):
                for property_name in PROPERTIES_OBJECT:
                    if item_key == property_name and isinstance(original_data[item][property_name], dict):
                        if original_data[item][property_name].get("id"):
                            original_data[item][property_name] = original_data[item][property_name]["id"]
                if item_key in data[item].keys():
                    if item_key == "id" and len(data[item].keys()) > 1:
                        # Related nodes typically require an ID. So the ID is only
                        # removed if it's the last key in the current context
                        continue
                    variable_key = None
                    if isinstance(data[item][item_key], str):
                        variable_key = data[item][item_key][1:]

                    if original_data[item][item_key] == data[item][item_key]:
                        data[item].pop(item_key)
                    elif variable_key in variables and original_data[item][item_key] == variables[variable_key]:
                        data[item].pop(item_key)
                        variables.pop(variable_key)

        if not data[item]:
            data.pop(item)

    def _strip_unmodified(self, data: dict, variables: dict) -> Tuple[dict, dict]:
        original_data = self._data or {}
        for relationship in self._relationships:
            relationship_property = getattr(self, relationship)
            if relationship_property and not relationship_property.initialized and relationship in data:
                data.pop(relationship)
        for item in original_data.keys():
            if item in data.keys():
                if data[item] == original_data[item]:
                    data.pop(item)
                    continue
                if isinstance(original_data[item], dict):
                    self._strip_unmodified_dict(
                        data=data,
                        original_data=original_data,
                        variables=variables,
                        item=item,
                    )
                    if item in self._relationships and original_data[item].get("node"):
                        relationship_data_cardinality_one = copy(original_data)
                        relationship_data_cardinality_one[item] = original_data[item]["node"]
                        self._strip_unmodified_dict(
                            data=data,
                            original_data=relationship_data_cardinality_one,
                            variables=variables,
                            item=item,
                        )
                        # Run again to remove the "id" key if it's the last one remaining
                        self._strip_unmodified_dict(
                            data=data,
                            original_data=relationship_data_cardinality_one,
                            variables=variables,
                            item=item,
                        )

        return data, variables

    @staticmethod
    def _strip_alias(data: dict) -> Dict[str, Dict]:
        clean = {}

        for key, value in data.items():
            if "__alias__" in key:
                clean_key = key.split("__")[-1]
                clean[clean_key] = value
            else:
                clean[key] = value

        return clean

    def generate_query_data_init(
        self,
        filters: Optional[Dict[str, Any]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Union[Any, Dict]]:
        data: Dict[str, Any] = {
            "count": None,
            "edges": {"node": {"id": None, "display_label": None, "__typename": None}},
        }

        data["@filters"] = filters or {}

        if offset:
            data["@filters"]["offset"] = offset

        if limit:
            data["@filters"]["limit"] = limit

        if include and exclude:
            in_both, _, _ = compare_lists(include, exclude)
            if in_both:
                raise ValueError(f"{in_both} are part of both include and exclude")

        return data

    def generate_query_data_node(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        inherited: bool = True,
        insert_alias: bool = False,
    ) -> Dict[str, Union[Any, Dict]]:
        """Generate the node part of a GraphQL Query with attributes and nodes.

        Args:
            include (Optional[List[str]], optional): List of attributes or relationships to include. Defaults to None.
            exclude (Optional[List[str]], optional): List of attributes or relationships to exclude. Defaults to None.
            inherited (bool, optional): Indicated of the attributes and the relationships inherited from generics should be included as well. Defaults to True.

        Returns:
            Dict[str, Union[Any, Dict]]: Query in Dict format
        """
        # pylint: disable=too-many-branches

        data: Dict[str, Any] = {}

        for attr_name in self._attributes:
            if exclude and attr_name in exclude:
                continue

            attr: Attribute = getattr(self, attr_name)

            if not inherited and attr._schema.inherited:
                continue

            attr_data = attr._generate_query_data()
            if attr_data:
                data[attr_name] = attr_data
                if insert_alias:
                    data[attr_name]["@alias"] = f"__alias__{self._schema.kind}__{attr_name}"
            elif insert_alias:
                if insert_alias:
                    data[attr_name] = {"@alias": f"__alias__{self._schema.kind}__{attr_name}"}

        for rel_name in self._relationships:
            if exclude and rel_name in exclude:
                continue

            rel_schema = self._schema.get_relationship(name=rel_name)

            if not rel_schema or (not inherited and rel_schema.inherited):
                continue

            if (
                rel_schema.cardinality == RelationshipCardinality.MANY  # type: ignore[union-attr]
                and rel_schema.kind not in [RelationshipKind.ATTRIBUTE, RelationshipKind.PARENT]  # type: ignore[union-attr]
                and not (include and rel_name in include)
            ):
                continue

            if rel_schema and rel_schema.cardinality == "one":
                rel_data = RelatedNode._generate_query_data()
            elif rel_schema and rel_schema.cardinality == "many":
                rel_data = RelationshipManager._generate_query_data()
            data[rel_name] = rel_data
            if insert_alias:
                data[rel_name]["@alias"] = f"__alias__{self._schema.kind}__{rel_name}"

        return data

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
                raise FilterNotFound(
                    identifier=filter_name,
                    kind=self._schema.kind,
                    filters=valid_filters,
                )

        return True

    def extract(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Extract some datapoints defined in a flat notation."""
        result: Dict[str, Any] = {}
        for key, value in params.items():
            result[key] = get_flat_value(self, key=value)

        return result


class InfrahubNode(InfrahubNodeBase):
    def __init__(
        self,
        client: InfrahubClient,
        schema: Union[NodeSchema, GenericSchema],
        branch: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        self._client = client
        self.__class__ = type(f"{schema.kind}InfrahubNode", (self.__class__,), {})

        if isinstance(data, dict) and "node" in data:
            data = data.get("node")

        super().__init__(schema=schema, branch=branch or client.default_branch, data=data)

    @classmethod
    async def from_graphql(
        cls,
        client: InfrahubClient,
        branch: str,
        data: dict,
        schema: Optional[Union[NodeSchema, GenericSchema]] = None,
    ) -> Self:
        if not schema:
            node_kind = data.get("__typename", None) or data.get("node", {}).get("__typename", None)
            if not node_kind:
                raise ValueError("Unable to determine the type of the node, __typename not present in data")
            schema = await client.schema.get(kind=node_kind)

        return cls(client=client, schema=schema, branch=branch, data=cls._strip_alias(data))

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
                        name=rel_name,
                        client=self._client,
                        node=self,
                        branch=self._branch,
                        schema=rel_schema,
                        data=rel_data,
                    ),
                )

    async def delete(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        input_data = {"data": {"id": self.id}}
        mutation_query = {"ok": None}
        query = Mutation(
            mutation=f"{self._schema.kind}Delete",
            input_data=input_data,
            query=mutation_query,
        )
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-delete",
        )

    async def save(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        if self._existing is False:
            await self._create(at=at)
        else:
            await self._update(at=at)

        self._client.store.set(key=self.id, node=self)

    async def generate_query_data(
        self,
        filters: Optional[Dict[str, Any]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
    ) -> Dict[str, Union[Any, Dict]]:
        data = self.generate_query_data_init(
            filters=filters,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
        )
        data["edges"]["node"].update(self.generate_query_data_node(include=include, exclude=exclude, inherited=True))

        if isinstance(self._schema, GenericSchema) and fragment:
            for child in self._schema.used_by:
                child_schema = await self._client.schema.get(kind=child)
                child_node = InfrahubNode(client=self._client, schema=child_schema)

                # Add the attribute and the relationship already part of the parent to the exclude list for the children
                exclude_parent = self._attributes + self._relationships
                _, _, only_in_list2 = compare_lists(list1=include or [], list2=exclude_parent)

                exclude_child = only_in_list2
                if exclude:
                    exclude_child += exclude

                child_data = child_node.generate_query_data_node(
                    include=include,
                    exclude=exclude_child,
                    inherited=False,
                    insert_alias=True,
                )

                if child_data:
                    data["edges"]["node"][f"...on {child}"] = child_data

        return {self._schema.kind: data}

    async def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        input_data["data"]["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.kind}Create"
        query = Mutation(
            mutation=mutation_name,
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )
        await self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
            variables=input_data["variables"],
        )
        self._existing = True

    async def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data(update=True)
        input_data["data"]["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(
            mutation=f"{self._schema.kind}Update",
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
        self,
        client: InfrahubClientSync,
        schema: Union[NodeSchema, GenericSchema],
        branch: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        self.__class__ = type(f"{schema.kind}InfrahubNodeSync", (self.__class__,), {})
        self._client = client

        if isinstance(data, dict) and "node" in data:
            data = data.get("node")

        super().__init__(schema=schema, branch=branch or client.default_branch, data=data)

    @classmethod
    def from_graphql(
        cls,
        client: InfrahubClientSync,
        branch: str,
        data: dict,
        schema: Optional[Union[NodeSchema, GenericSchema]] = None,
    ) -> Self:
        if not schema:
            node_kind = data.get("__typename", None) or data.get("node", {}).get("__typename", None)
            if not node_kind:
                raise ValueError("Unable to determine the type of the node, __typename not present in data")
            schema = client.schema.get(kind=node_kind)

        return cls(client=client, schema=schema, branch=branch, data=cls._strip_alias(data))

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
                        name=rel_name,
                        client=self._client,
                        node=self,
                        branch=self._branch,
                        schema=rel_schema,
                        data=rel_data,
                    ),
                )

    def delete(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        input_data = {"data": {"id": self.id}}
        mutation_query = {"ok": None}
        query = Mutation(
            mutation=f"{self._schema.kind}Delete",
            input_data=input_data,
            query=mutation_query,
        )
        self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-delete",
        )

    def save(self, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)
        if self._existing is False:
            self._create(at=at)
        else:
            self._update(at=at)

    def generate_query_data(
        self,
        filters: Optional[Dict[str, Any]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
    ) -> Dict[str, Union[Any, Dict]]:
        data = self.generate_query_data_init(
            filters=filters,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
        )
        data["edges"]["node"].update(self.generate_query_data_node(include=include, exclude=exclude, inherited=True))

        if isinstance(self._schema, GenericSchema) and fragment:
            for parent in self._schema.used_by:
                parent_schema = self._client.schema.get(kind=parent)
                parent_node = InfrahubNodeSync(client=self._client, schema=parent_schema)
                parent_data = parent_node.generate_query_data_node(
                    include=include, exclude=exclude, inherited=False, insert_alias=True
                )
                if parent_data:
                    data["edges"]["node"][f"...on {parent}"] = parent_data

        return {self._schema.kind: data}

    def _create(self, at: Timestamp) -> None:
        input_data = self._generate_input_data()
        mutation_query = {"ok": None, "object": {"id": None}}
        mutation_name = f"{self._schema.kind}Create"
        query = Mutation(
            mutation=mutation_name,
            input_data=input_data["data"],
            query=mutation_query,
            variables=input_data["mutation_variables"],
        )

        self._client.execute_graphql(
            query=query.render(),
            branch_name=self._branch,
            at=at,
            tracker=f"mutation-{str(self._schema.kind).lower()}-create",
            variables=input_data["variables"],
        )
        self._existing = True

    def _update(self, at: Timestamp) -> None:
        input_data = self._generate_input_data(update=True)
        input_data["data"]["data"]["id"] = self.id
        mutation_query = {"ok": None, "object": {"id": None}}
        query = Mutation(
            mutation=f"{self._schema.kind}Update",
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
                node_class(
                    name=external_name,
                    branch=node._branch,
                    client=node._client,
                    schema=schema,
                    data=value,
                ),
            )

    return prop
