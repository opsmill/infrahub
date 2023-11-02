import ipaddress
import itertools
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

import ruamel.yaml
from infrahub_sdk import Config, InfrahubClientSync, InfrahubNodeSync, NodeSchema
from nornir.core.inventory import (
    ConnectionOptions,
    Defaults,
    Group,
    Groups,
    Host,
    HostOrGroup,
    Hosts,
    Inventory,
    ParentGroups,
)
from pydantic import BaseModel, Field, validator
from pydantic.dataclasses import dataclass
from slugify import slugify

logger = logging.getLogger(__name__)


def ip_interface_to_ip_string(ip_interface: Union[ipaddress.IPv4Interface, ipaddress.IPv6Interface]) -> str:
    return str(ip_interface.ip)


def resolve_node_mapping(node: InfrahubNodeSync, attrs: List[str]) -> Any:
    for attr in attrs:
        if attr in node._schema.relationship_names:
            relation = getattr(node, attr)
            if relation.schema.cardinality == "many":
                raise RuntimeError("Relations with many cardinality are not supported!")
            node = relation.peer
        elif attr in node._schema.attribute_names:
            node_attr = getattr(node, attr)
            value_mapper: Dict[str, Callable] = {
                "IPHost": ip_interface_to_ip_string,
            }
            mapper = value_mapper.get(node_attr._schema.kind, lambda value: value)
            return mapper(node_attr.value)
    raise RuntimeError("Unable to resolve mapping")


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


@dataclass
class SchemaMappingNode:
    name: str
    mapping: str


# pylint: disable=E0213
class HostNode(BaseModel):
    kind: str
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)

    @validator("include", always=True)
    def validate_include(cls, v: List[str]):
        # add member_of_groups to include property
        # this relation needs to be pre fetched to be able to determine the group membership of a HostNode
        include = ["member_of_groups"]
        for item in v:
            include.append(item)
        return include


def get_related_nodes(node_schema: NodeSchema, attrs: Set[str]) -> Set[str]:
    nodes = {"CoreStandardGroup"}
    relationship_schemas = {schema.name: schema.peer for schema in node_schema.relationships}
    for attr in attrs:
        if attr in relationship_schemas:
            nodes.add(relationship_schemas[attr])
    return nodes


class InfrahubInventory:
    """
    Inventory pluging for `Opsmill - Infrahub <https://github.com/opsmill/infrahub>`

    Arguments:
        address: Infrahub url (defaults to ``http://localhost:8000``)
        branch: Infrahub branch to use (defaults to ``main``)
        host_node: Infrahub Node type that will map to a Nornir Host
        schema_mappings:
        group_mapping: Definiton of relations and attributes to extract groups from
        defaults_file: Path to defaults file (defaults to ``defaults.yaml``)
        group_file: Path to group file (defaults to ``group.yaml``)
    """

    def __init__(
        self,
        host_node: Dict[str, Any],
        address: str = "http://localhost:8000",
        token: Optional[str] = None,
        branch: str = "main",
        schema_mappings: Optional[List[Dict[str, str]]] = None,
        group_mappings: Optional[List[str]] = None,
        defaults_file: str = "defaults.yaml",
        group_file: str = "group.yaml",
    ):
        self.address = address
        self.branch = branch

        self.host_node = HostNode(**host_node)

        self.defaults_file = Path(defaults_file).expanduser()
        self.group_file = Path(group_file).expanduser()

        self.client = InfrahubClientSync.init(config=Config(api_token=token), address=self.address)

        schema_mappings = schema_mappings or []
        self.schema_mappings = [SchemaMappingNode(**mapping) for mapping in schema_mappings]

        group_mappings = group_mappings or []
        self.group_mappings = group_mappings

        host_node_schema = self.client.schema.get(kind=self.host_node.kind)

        attrs = set(
            itertools.chain(
                [schema_mapping.mapping.split(".")[0] for schema_mapping in self.schema_mappings],
                [group_mapping.split(".")[0] for group_mapping in self.group_mappings],
            )
        )
        self.extra_nodes = get_related_nodes(host_node_schema, attrs)

    def load(self) -> Inventory:
        yml = ruamel.yaml.YAML(typ="safe")

        hosts = Hosts()
        groups = Groups()
        defaults = Defaults()

        defaults_dict: Dict[str, Any] = {}
        groups_dict: Dict[str, Any] = {}

        if self.defaults_file.exists():
            with self.defaults_file.open("r", encoding="utf-8") as f:
                defaults_dict = yml.load(f) or {}

        defaults = _get_defaults(defaults_dict)

        if self.group_file.exists():
            with self.group_file.open("r", encoding="utf-8") as f:
                groups_dict = yml.load(f) or {}

        for n, g in groups_dict.items():
            groups[n] = _get_inventory_element(Group, g, n, defaults)

        for g in groups.values():
            g.groups = ParentGroups([groups[g] for g in g.groups])

        host: Dict[str, Any] = {}

        for extra_node in self.extra_nodes:
            self.get_resources(kind=extra_node)

        host_nodes = self.get_resources(**dict(self.host_node))

        for host_node in host_nodes:
            name = host_node.name.value

            for schema_mapping in self.schema_mappings:
                attrs = schema_mapping.mapping.split(".")

                try:
                    host[schema_mapping.name] = resolve_node_mapping(host_node, attrs)
                except RuntimeError:
                    # TODO: what do we do in this case?
                    continue

            host["data"] = {"InfrahubNode": host_node}
            hosts[name] = _get_inventory_element(Host, host, name, defaults)

            extracted_groups = [related_node.peer.name.value for related_node in host_node.member_of_groups.peers]

            for group_mapping in self.group_mappings:
                attrs = group_mapping.split(".")

                try:
                    extracted_groups.append(f"{attrs[0]}__{slugify(resolve_node_mapping(host_node, attrs))}")
                except RuntimeError:
                    print(f"Unable to extract group for {attrs}")
                    # TODO: what do we do in this case?
                    continue

            for group in extracted_groups:
                if group not in groups.keys():
                    groups[group] = _get_inventory_element(Group, {}, group, defaults)

            hosts[name].groups = ParentGroups([groups[g] for g in extracted_groups])

        return Inventory(hosts=hosts, groups=groups, defaults=defaults)

    def get_resources(self, kind: str, **kwargs) -> List[InfrahubNodeSync]:
        filters = {}
        if "filters" in kwargs:
            filters = kwargs.pop("filters")

        resources = self.client.all(kind=kind, branch=self.branch, populate_store=True, **kwargs, **filters)
        return resources
