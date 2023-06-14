import logging

from typing import Any
from typing import Dict
from typing import List
from typing import Type
from pathlib import Path

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
from infrahub_client import InfrahubClientSync
from infrahub_client import InfrahubNodeSync

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


class InfrahubInventory:
    """
    Inventory pluging for `Opsmill - Infrahub <https://github.com/opsmill/infrahub>`

    Arguments:
        address: Infrahub url (defaults to ``http://localhost:8000``)
        defaults_file: Path to defaults file (defaults to ``defaults.yaml``)
    """

    def __init__(
        self,
        address: str = "http://localhost:8000",
        defaults_file: str = "defaults.yaml",
    ):
        self.address = address
        self.defaults_file = Path(defaults_file).expanduser()
        self.client = InfrahubClientSync.init(address=self.address)

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


        return Inventory(hosts=hosts, groups=groups, defaults=defaults)

    def get_resources(self, kind: str) -> InfrahubNodeSync:
        resources = self.client.all(kind=kind, populate_store=True)
        return resources
