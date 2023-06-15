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
        group_extractors: Optional[List[Dict[str, str]]] = None,
        defaults_file: str = "defaults.yaml",
        group_file: str = "group.yaml"
    ):
        self.address = address
        self.branch = branch
        self.defaults_file = Path(defaults_file).expanduser()
        self.group_file = Path(group_file).expanduser()
        self.client = InfrahubClientSync.init(address=self.address)

        self.group_extractors = []

        if group_extractors is None:
            group_extractors = []

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

        host_node = "Device"
        extra_nodes = ("Platform", "Location", "IPAddress")

        infrahub_hosts = self.get_resources(kind=host_node)

        for node in extra_nodes:
            self.get_resources(kind=node)

        for node in infrahub_hosts:
            name = node.name.value

            try:
                hostname = node.primary_address.display_label.split("/")[0]
            except AttributeError as e:
                logger.warn(f"Device node <{name}> is not configured with a primary address")
                hostname = None

            host["hostname"] = hostname

            try:
                platform = node.platform.peer.nornir_platform.value
            except AttributeError as e:
                logger.warn(f"Device node <{name}> is not configured with a platform!")
                platform = None

            host["platform"] = platform
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
