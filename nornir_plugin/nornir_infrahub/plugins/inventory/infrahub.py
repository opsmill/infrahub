import logging

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

from nornir.core.inventory import ConnectionOptions
from nornir.core.inventory import Defaults
from nornir.core.inventory import Group
from nornir.core.inventory import Groups
from nornir.core.inventory import Host
from nornir.core.inventory import HostOrGroup
from nornir.core.inventory import Hosts
from nornir.core.inventory import Inventory
from nornir.core.inventory import ParentGroups

import ruamel.yaml
from pydantic import BaseModel
from infrahub_client import InfrahubClientSync
from infrahub_client import InfrahubNodeSync
from infrahub_client import NodeSchema
from infrahub_client.node import Attribute
from infrahub_client.node import RelatedNodeSync

logger = logging.getLogger(__name__)


def _get_connection_options(data: Dict[str, Any]) -> Dict[str, ConnectionOptions]:
    cp = {}
    for cn, c in data.items():
        cp[cn] = ConnectionOptions(
            hostname=c.get("hostname"),
            port=c.get("port"),
            username=c.get("username"),
            password=c.get("password"),
            platform=c.get("platform"),
            extras=c.get("extras"),
        )
    return cp


def _get_defaults(data: Dict[str, Any]) -> Defaults:
    return Defaults(
        hostname=data.get("hostname"),
        port=data.get("port"),
        username=data.get("username"),
        password=data.get("password"),
        platform=data.get("platform"),
        data=data.get("data"),
        connection_options=_get_connection_options(data.get("connection_options", {})),
    )


def _get_inventory_element(typ: Type[HostOrGroup], data: Dict[str, Any], name: str, defaults: Defaults) -> HostOrGroup:
    return typ(
        name=name,
        hostname=data.get("hostname"),
        port=data.get("port"),
        username=data.get("username"),
        password=data.get("password"),
        platform=data.get("platform"),
        data=data.get("data"),
        groups=data.get("groups"),  # this is a hack, we will convert it later to the correct type
        defaults=defaults,
        connection_options=_get_connection_options(data.get("connection_options", {})),
    )

class SchemaMappingNode(BaseModel):
    name: str
    mapping: str

def get_related_nodes(node_schema: NodeSchema, attrs: List[str]) -> List[str]:
    nodes = []
    for attr in attrs:
        if attr in node_schema.attribute_names:
            continue
        for rel_schema in node_schema.relationships:
            if rel_schema.name == attr:
                nodes.append(rel_schema.peer)
                break
    return nodes

class GroupExtractorException(Exception):
    pass

class RelationGroupExtractor(BaseModel):
    name: str
    attribute: str
    type: str

    def extract(self, node):
        try:
            relation = getattr(node, self.name)
            value = getattr(relation.peer, self.attribute).value
        except AttributeError:
            raise GroupExtractorException(f"Unable to resolve relation {self.name}")
        return f"{self.name}__{value}"

class AttributeGroupExtractor(BaseModel):
    name: str
    type: str

    def extract(self, node):
        try:
            attribute = getattr(node, self.name)
        except AttributeError:
            raise GroupExtractorException(f"Unable to retrieve attribute {self.name}")

        if not isinstance(attribute, Attribute):
            raise GroupExtractorException(f"Unable to retrieve attribute {self.name}")
        return f"{self.name}__{attribute.value}"


class InfrahubInventory:
    """
    Inventory pluging for `Opsmill - Infrahub <https://github.com/opsmill/infrahub>`

    Arguments:
        address: Infrahub url (defaults to ``http://localhost:8000``)
        branch: Infrahub branch to use (defaults to ``main``)
        group_extractors: Definiton of relations and attributes to extract groups from
        defaults_file: Path to defaults file (defaults to ``defaults.yaml``)
        group_file: Path to group file (defaults to ``group.yaml``)
    """

    def __init__(
        self,
        address: str = "http://localhost:8000",
        branch: str = "main",
        host_node: str = "Device",
        schema_mapping: Optional[Dict[str, str]] = None,
        group_extractors: Optional[List[Dict[str, str]]] = None,
        defaults_file: str = "defaults.yaml",
        group_file: str = "group.yaml"
    ):
        self.address = address
        self.branch = branch
        self.host_node = host_node
        self.defaults_file = Path(defaults_file).expanduser()
        self.group_file = Path(group_file).expanduser()
        self.client = InfrahubClientSync.init(address=self.address)

        self.schema_mapping = [
            SchemaMappingNode(**mapping)
            for mapping in schema_mapping
        ]

        host_node_schema = self.client.schema.get(kind=host_node)

        attrs = [mapping.mapping.split(".")[0] for mapping in self.schema_mapping]
        self.extra_nodes = get_related_nodes(host_node_schema, attrs)

        self.group_extractors = []
        group_extractors = group_extractors or []

        for extractor in group_extractors:
            if extractor.get("type") == "relation":
                self.group_extractors.append(RelationGroupExtractor(**extractor))
            elif extractor.get("type") == "attribute":
                self.group_extractors.append(AttributeGroupExtractor(**extractor))


    def load(self) -> Inventory:
        yml = ruamel.yaml.YAML(typ="safe")

        hosts = Hosts()
        groups = Groups()
        defaults = Defaults()

        defaults_dict: Dict[str, Any] = {}
        groups_dict: Dict[str, Any] = {}

        if self.defaults_file.exists():
            with self.defaults_file.open("r") as f:
                defaults_dict = yml.load(f) or {}

        defaults = _get_defaults(defaults_dict)

        if self.group_file.exists():
            with self.group_file.open("r") as f:
                groups_dict = yml.load(f) or {}

        for n, g in groups_dict.items():
            groups[n] = _get_inventory_element(Group, g, n, defaults)

        for g in groups.values():
            g.groups = ParentGroups([groups[g] for g in g.groups])

        host: Dict[str, Any] = {}

        for node in self.extra_nodes:
            self.get_resources(kind=node)

        host_nodes = self.get_resources(kind=self.host_node)

        for node in host_nodes:
            # breakpoint()
            name = node.name.value

            for mapping in self.schema_mapping:

                current_node = node
                attrs = mapping.mapping.split(".")

                for attr in attrs:
                    if attr in current_node._schema.attribute_names:
                        node_attr = getattr(current_node, attr)
                        host[mapping.name] = node_attr.value
                    elif attr in current_node._schema.relationship_names:
                        relation = getattr(current_node, attr)
                        if relation.schema.cardinality == "many":
                            # TODO: what do we do in this case?
                            raise RuntimeError("Relations with many cardinality are not supported!")
                        current_node = relation.peer

            host["data"] = {"InfrahubNode": node}
            hosts[name] = _get_inventory_element(Host, host, name, defaults)

            extracted_groups = self.extract_node_groups(node)

            for group in extracted_groups:
                if group not in groups.keys():
                    groups[group] = _get_inventory_element(Group, {}, group, defaults)

            hosts[name].groups = ParentGroups([groups[g] for g in extracted_groups])

        return Inventory(hosts=hosts, groups=groups, defaults=defaults)

    def extract_node_groups(self, node: InfrahubNodeSync) -> List[str]:
        groups = []
        for group_extractor in self.group_extractors:
            try:
                groups.append(group_extractor.extract(node))
            except GroupExtractorException:
                continue
        return groups

    def get_resources(self, kind: str) -> InfrahubNodeSync:
        resources = self.client.all(kind=kind, branch=self.branch, populate_store=True)
        return resources
