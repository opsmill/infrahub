from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_client.exceptions import FilterNotFound
from infrahub_client.graphql import Mutation
from infrahub_client.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub_client.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_client.client import InfrahubClient


class InfrahubNode:
    def __init__(
        self, client: InfrahubClient, schema: NodeSchema, branch: Optional[str] = None, data: Optional[dict] = None
    ) -> None:
        self._client = client
        self._schema = schema
        self._data = data

        self._branch = branch or self._client.default_branch

        self.id: Optional[str] = data.get("id", None) if isinstance(data, dict) else None
        self.display_label: Optional[str] = data.get("display_label", None) if isinstance(data, dict) else None

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
                setattr(self.__class__, rel_name, generate_relationship_property(rel_name))
                setattr(self, rel_name, rel_data)
            else:
                setattr(self, rel_name, RelationshipManager(name=rel_name, schema=rel_schema, data=rel_data))

    def __repr__(self) -> str:
        if self.display_label:
            return self.display_label
        if not self.id:
            return f"{self._schema.kind} (no id yet)"

        return f"{self._schema.kind} ({self.id})"

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
                raise FilterNotFound(identifier=filter_name, kind=self._schema.kind)

        return True


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
        self.source: Optional[str] = data.get("source", None)
        self.owner: Optional[str] = data.get("owner", None)

    def _generate_input_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {}

        if self.value is not None:
            data["value"] = self.value

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[prop_name] = getattr(self, prop_name)

        return data

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"value": None}

        for prop_name in self._properties_flag:
            data[prop_name] = None
        for prop_name in self._properties_object:
            data[prop_name] = {"id": None, "display_label": None}

        return data


class RelatedNode:
    def __init__(self, schema: RelationshipSchema, data: Union[Any, dict], name: Optional[str] = None):
        self.schema = schema
        self.name = name

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        self.peer = None

        if isinstance(data, InfrahubNode):
            self.peer = data
            data = {"id": self.peer.id}
        elif not isinstance(data, dict):
            data = {"id": data}

        self.id: Optional[str] = data.get("id", None)
        self.display_label = data.get("display_label", None)
        self.updated_at: Optional[bool] = data.get("_relation__updated_at", None)

        for prop in self._properties:
            if value := data.get(prop, None):
                setattr(self, prop, value)
                continue

            setattr(self, prop, data.get(f"_relation__{prop}", None))

    def _generate_input_data(self) -> Dict[str, Any]:
        data = {}

        if self.id is not None:
            data["id"] = self.id

        for prop_name in self._properties:
            if getattr(self, prop_name) is not None:
                data[f"_relation__{prop_name}"] = getattr(self, prop_name)

        return data

    def _generate_query_data(self) -> Optional[Dict]:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        for prop_name in self._properties_flag:
            data[f"_relation__{prop_name}"] = None
        for prop_name in self._properties_object:
            data[f"_relation__{prop_name}"] = {"id": None, "display_label": None}

        return data


class RelationshipManager:
    def __init__(self, name: str, schema: RelationshipSchema, data: Union[Any, dict]):
        self.name = name
        self.schema = schema
        self.peers: List[RelatedNode] = []

        self._properties_flag = ["is_visible", "is_protected"]
        self._properties_object = ["source", "owner"]
        self._properties = self._properties_flag + self._properties_object

        if data is None:
            return

        if not isinstance(data, list):
            raise ValueError(f"{name} found a {type(data)} instead of a list")

        for item in data:
            self.peers.append(RelatedNode(name=name, schema=schema, data=item))

    def add(self, data: Union[str, RelatedNode, dict]) -> None:
        """Add a new peer to this relationship.
        Need to check if the peer is already present
        """

        # TODO add some check to ensure
        # that we are not adding a node that already exist
        self.peers.append(RelatedNode(schema=self.schema, data=data))

    def remove(self, data: Any) -> None:
        pass

    def _generate_input_data(self) -> List[Dict]:
        return [peer._generate_input_data() for peer in self.peers]

    def _generate_query_data(self) -> Dict:
        data: Dict[str, Any] = {"id": None, "display_label": None}

        for prop_name in self._properties_flag:
            data[f"_relation__{prop_name}"] = None
        for prop_name in self._properties_object:
            data[f"_relation__{prop_name}"] = {"id": None, "display_label": None}

        return data


def generate_relationship_property(name: str):  # type: ignore
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
            setattr(self, internal_name, RelatedNode(name=external_name, schema=schema, data=value))

    return prop
