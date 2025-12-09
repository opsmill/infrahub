import copy
import logging
import time
import uuid
from collections import defaultdict
from enum import StrEnum
from ipaddress import IPv4Network, IPv6Network
from typing import cast

from infrahub_sdk import InfrahubClient
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.protocols import (
    BuiltinTag,
    CoreAccount,
    CoreAccountGroup,
    CoreAccountRole,
    CoreGlobalPermission,
    CoreIPAddressPool,
    CoreIPPrefixPool,
    CoreObjectPermission,
    CoreStandardGroup,
    IpamNamespace,
)
from infrahub_sdk.protocols_base import CoreNode
from infrahub_sdk.types import Order
from infrahub_sdk.uuidt import UUIDT
from protocols import (
    InfraAutonomousSystem,
    InfraBGPPeerGroup,
    InfraBGPSession,
    InfraCircuit,
    InfraCircuitEndpoint,
    InfraDevice,
    InfraInterfaceL2,
    InfraInterfaceL3,
    InfraLagInterfaceL2,
    InfraMlagDomain,
    InfraMlagInterfaceL2,
    InfraPlatform,
    InfraVLAN,
    IpamIPAddress,
    IpamIPPrefix,
    LocationContinent,
    LocationCountry,
    LocationSite,
    OrganizationProvider,
)
from pydantic import BaseModel, ConfigDict, Field

PROFILES = {
    "small": {"num_sites": 2, "num_device_per_site": 6, "has_bgp_mesh": False, "has_branch": False},
    "medium": {"num_sites": 5, "num_device_per_site": 6, "has_bgp_mesh": True, "has_branch": True},
    "large": {"num_sites": 10, "num_device_per_site": 26, "has_bgp_mesh": False, "has_branch": False},
    "x-large": {"num_sites": 50, "num_device_per_site": 52, "has_bgp_mesh": False, "has_branch": False},
    "xx-large": {"num_sites": 100, "num_device_per_site": 102, "has_bgp_mesh": False, "has_branch": False},
    "ultimate": {"num_sites": 200, "num_device_per_site": 204, "has_bgp_mesh": True, "has_branch": True},
}


class ConfigError(Exception):
    pass


# Define the global configuration object
class GlobalConfig:
    def __init__(self) -> None:
        self.default_profile_name = "medium"
        self.num_sites = None
        self.num_device_per_site = None
        self.has_bgp_mesh = False
        self.has_branch = False

    def __set_config(self, num_sites: int, num_device_per_site: int, has_bgp_mesh: bool, has_branch: bool) -> None:
        # TODO: I guess it could be defined in the attribute itself?
        # Ensure that num_site is between boudaries
        if 2 <= int(num_sites) <= 200:
            self.num_sites = int(num_sites)
        else:
            raise ConfigError(f"Value for `num_sites` ({num_sites}) should be between 2 and 200.")

        # Ensure that num_device_per_site is between boudaries
        if 6 <= int(num_device_per_site) <= 204:
            self.num_device_per_site = int(num_device_per_site)
        else:
            raise ConfigError(f"Value for `num_device_per_site` ({num_device_per_site}) should be between 6 and 204.")

        self.has_bgp_mesh = has_bgp_mesh
        self.has_branch = has_branch

    def load_config(
        self,
        profile: str | None = None,
        num_sites: int | None = None,
        num_device_per_site: int | None = None,
        has_bgp_mesh: bool | None = None,
        has_branch: bool | None = None,
    ) -> None:
        if profile:
            # Warn user that we are going to ignore his input
            if num_sites or num_device_per_site or has_bgp_mesh or has_branch:
                raise ConfigError("You can't set additional config items if you've already provided a profile.")

            # Make sure profile exists
            if profile not in PROFILES:
                raise ConfigError(
                    f"Value for profile ({profile}) doesn't exist, please pick one among {PROFILES.keys()}."
                )

            # Load prebuilt profile
            profile_obj: dict = PROFILES[profile]
            self.__set_config(
                profile_obj["num_sites"],
                profile_obj["num_device_per_site"],
                profile_obj["has_bgp_mesh"],
                profile_obj["has_branch"],
            )
        else:
            # Load from manual arguments, if provided
            # If user only provides a part of the arguments e.g. only `number of site`
            # we fall back on medium profile by default
            default_profile: dict = PROFILES[self.default_profile_name]

            self.__set_config(
                num_sites=num_sites if num_sites is not None else default_profile["num_sites"],
                num_device_per_site=num_device_per_site
                if num_device_per_site is not None
                else default_profile["num_device_per_site"],
                has_bgp_mesh=has_bgp_mesh if has_bgp_mesh is not None else default_profile["has_bgp_mesh"],
                has_branch=has_branch if has_branch is not None else default_profile["has_branch"],
            )

    def __repr__(self) -> str:
        return f"Config(Sites: {self.num_sites}, Devices per site: {self.num_device_per_site}, BGP mesh: {self.has_bgp_mesh}, Additional branches: {self.has_branch})"


def translate_str_to_bool(key: str, value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise TypeError(f"Value for {key} should be 'True' or 'False'")


class AccountRole(BaseModel):
    name: str
    global_permissions: list[str] | str | None = None
    object_permissions: list[str] | str | None = None


class AccountGroup(BaseModel):
    name: str
    roles: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)


class Account(BaseModel):
    name: str
    label: str
    password: str
    account_type: str


class GlobalPermission(BaseModel):
    action: str
    decision: int


class ObjectPermission(BaseModel):
    namespace: str
    name: str
    action: str
    decision: int


class Asn(BaseModel):
    asn: int
    organization: str

    @property
    def name(self) -> str:
        return f"AS{self.asn}"


class BgpPeerGroup(BaseModel):
    name: str
    import_policies: str
    export_policies: str
    local_as: str
    remote_as: str | None = Field(default=None)


class Device(BaseModel):
    name: str
    status: str
    type: str
    profile: str
    role: str
    tags: list[str]
    platform: str
    _idx: int

    @property
    def l2_interface_names(self) -> list[str]:
        INTERFACE_L2_NAMES = {
            "7280R3": ["Ethernet11", "Ethernet12"],
            "ASR1002-HX": ["Ethernet11", "Ethernet12"],
            "MX204": ["et-0/0/3"],
            "7010TX-48": [f"Ethernet{idx}" for idx in range(1, 49)],
        }

        return INTERFACE_L2_NAMES.get(self.type, [])

    @property
    def l3_interface_names(self) -> list[str]:
        INTERFACE_L3_NAMES = {
            "7280R3": [
                "Ethernet1",
                "Ethernet2",
                "Ethernet3",
                "Ethernet4",
                "Ethernet5",
                "Ethernet6",
                "Ethernet7",
                "Ethernet8",
                "Ethernet9",
                "Ethernet10",
            ],
            "ASR1002-HX": [
                "Ethernet1",
                "Ethernet2",
                "Ethernet3",
                "Ethernet4",
                "Ethernet5",
                "Ethernet6",
                "Ethernet7",
                "Ethernet8",
                "Ethernet9",
                "Ethernet10",
            ],
            "7010TX-48": [],
            "MX204": ["et-0/0/0", "et-0/0/1", "et-0/0/2"],
        }
        return INTERFACE_L3_NAMES.get(self.type, [])


class Group(BaseModel):
    name: str
    label: str


class InterfaceProfile(BaseModel):
    name: str
    mtu: int
    kind: str

    @property
    def profile_kind(self) -> str:
        return f"Profile{self.kind}"


class P2pNetwork(BaseModel):
    site1: str
    site2: str
    edge: int
    circuit: str
    pool: IpamIPPrefix | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def identifier(self) -> str:
        return f"{self.site1_device}__{self.site2_device}"

    @property
    def site1_device(self) -> str:
        return f"{self.site1}-edge{self.edge}"

    @property
    def site2_device(self) -> str:
        return f"{self.site2}-edge{self.edge}"

    @property
    def provider_name(self) -> str:
        if self.edge == 1:
            return "Lumen"
        return "Zayo"

    def get_pool(self) -> IpamIPPrefix:
        if self.pool:
            return self.pool
        raise Exception("the variable pool hasn't been initilized yet")


class Platform(BaseModel):
    name: str
    nornir_platform: str
    napalm_driver: str
    netmiko_device_type: str
    ansible_network_os: str


class Organization(BaseModel):
    name: str
    type: str

    @property
    def kind(self) -> str:
        return f"Organization{self.type.title()}"


class Site(BaseModel):
    name: str
    country: str
    city: str
    contact: str


class Vlan(BaseModel):
    id: int
    role: str


class TemplateInfraFrontPatchPanelInterface(BaseModel):
    template_name: str
    name: str
    connector_type: str
    description: str
    patch_panel: dict


class TemplateInfraPatchPanel(BaseModel):
    template_name: str
    module_capacity: int
    description: str
    tags: list[str]
    interfaces: list[TemplateInfraFrontPatchPanelInterface]


TEMPLATES = [
    TemplateInfraPatchPanel(
        template_name="Regular_Patch_Panel",
        module_capacity=3,
        description="Patch Panel used to connect racks",
        tags=["green"],
        interfaces=[
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P01",
                name="C1.P01",
                connector_type="LC",
                description="Position 1 on Module C1",
                patch_panel={},
            ),
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P02",
                name="C1.P02",
                connector_type="LC",
                description="Position 2 on Module C1",
                patch_panel={},
            ),
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P03",
                name="C1.P03",
                connector_type="LC",
                description="Position 3 on Module C1",
                patch_panel={},
            ),
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P04",
                name="C1.P04",
                connector_type="LC",
                description="Position 4 on Module C1",
                patch_panel={},
            ),
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P05",
                name="C1.P05",
                connector_type="LC",
                description="Position 5 on Module C1",
                patch_panel={},
            ),
            TemplateInfraFrontPatchPanelInterface(
                template_name="Regular_Patch_Panel__C1.P06",
                name="C1.P06",
                connector_type="LC",
                description="Position 6 on Module C1",
                patch_panel={},
            ),
        ],
    ),
]

CONTINENT_COUNTRIES = {
    "North America": ["United States of America", "Canada"],
    "South America": ["Mexico", "Brazil"],
    "Africa": ["Morocco", "Senegal"],
    "Europe": ["France", "Spain", "Italy"],
    "Asia": ["Japan", "China"],
    "Oceania": ["Australia", "New Zealand"],
}

SITES = [
    Site(name="atl", country="United States of America", city="Atlanta", contact="Bailey Li"),
    Site(name="ord", country="United States of America", city="Chicago", contact="Kayden Kennedy"),
    Site(name="jfk", country="United States of America", city="New York", contact="Micaela Marsh"),
    Site(name="den", country="United States of America", city="Denver", contact="Francesca Wilcox"),
    Site(name="dfw", country="United States of America", city="Dallas", contact="Carmelo Moran"),
    Site(name="iad", country="United States of America", city="Washington D.C.", contact="Avery Jimenez"),
    Site(name="sea", country="United States of America", city="Seattle", contact="Charlotte Little"),
    Site(name="sfo", country="United States of America", city="San Francisco", contact="Taliyah Sampson"),
    Site(name="iah", country="United States of America", city="Houston", contact="Fernanda Solomon"),
    Site(name="mco", country="United States of America", city="Orlando", contact="Arthur Rose"),
]

PLATFORMS = (
    Platform(
        name="Cisco IOS",
        nornir_platform="ios",
        napalm_driver="ios",
        netmiko_device_type="cisco_ios",
        ansible_network_os="ios",
    ),
    Platform(
        name="Cisco NXOS SSH",
        nornir_platform="nxos_ssh",
        napalm_driver="nxos_ssh",
        netmiko_device_type="cisco_nxos",
        ansible_network_os="nxos",
    ),
    Platform(
        name="Juniper JunOS",
        nornir_platform="junos",
        napalm_driver="junos",
        netmiko_device_type="juniper_junos",
        ansible_network_os="junos",
    ),
    Platform(
        name="Arista EOS",
        nornir_platform="eos",
        napalm_driver="eos",
        netmiko_device_type="arista_eos",
        ansible_network_os="eos",
    ),
)


class DevicePatternName(StrEnum):
    LEAF = "LEAF"
    CORE = "CORE"
    EDGE = "EDGE"


DEVICE_PATTERNS = {  # TODO: Maybe good candidate for template
    DevicePatternName.LEAF: Device(
        name="leaf",
        status="active",
        type="7010TX-48",
        profile="profile1",
        role="leaf",
        tags=["red", "green"],
        platform="Cisco IOS",
    ),
    DevicePatternName.CORE: Device(
        name="core",
        status="active",
        type="MX204",
        profile="profile1",
        role="core",
        tags=["blue"],
        platform="Juniper JunOS",
    ),
    DevicePatternName.EDGE: Device(
        name="edge",
        status="active",
        type="7280R3",
        profile="profile1",
        role="edge",
        tags=["red", "green"],
        platform="Arista EOS",
    ),
}

DEVICE_STATUSES = ["active", "provisioning", "drained"]


class SiteDesign:
    def __init__(self, number_of_device: int) -> None:
        """Takes the number of devices that need to be created on a given site.
        This method will decide how many device of each type to create and return all those objects as a list."""
        if number_of_device > 0:
            self.number_of_device = number_of_device
        else:
            raise ValueError("number_of_device must be non-negative")

        # There is a special case where there are 6 device...
        if number_of_device == 6:
            # Two of each
            self.num_edge_device = 2
            self.num_core_device = 2
            self.num_leaf_device = 2

        # Otherwise we try to compute something that makes a little bit of sense...
        else:
            # First we decide how many edge device we will spin
            # The rule is the following:
            # - between 0 -> 50 = 2 edges
            # - then we add 2 edges every 50 devices
            num_edge_device: int = 2
            num_edge_device += (self.number_of_device // 50) * 2
            self.num_edge_device = num_edge_device

            # Second goes core device, we take one third of the remaining device allocation
            self.num_core_device: int = (self.number_of_device - self.num_edge_device) // 3

            # Finally we allocate what's remaining as leaf
            self.num_leaf_device: int = self.number_of_device - self.num_edge_device - self.num_core_device

    def device_generator(self, number: int, device_pattern_name: DevicePatternName) -> list[Device]:
        """Generate a list of devices following the pattern provided."""
        result: list[Device] = []

        for i in range(1, number + 1):
            # Take the pattern as baseline
            current_device: Device = copy.copy(DEVICE_PATTERNS[device_pattern_name])

            # Start the tweaking
            current_device.name += str(i)
            current_device._idx = i

            # Add it to the list
            result.append(current_device)

        # Return devices
        return result

    def implement(self) -> list[Device]:
        # Build the list of device
        result: list[Device] = []

        # Generate the list and return it
        result.extend(self.device_generator(self.num_edge_device, DevicePatternName.EDGE))
        result.extend(self.device_generator(self.num_core_device, DevicePatternName.CORE))
        result.extend(self.device_generator(self.num_leaf_device, DevicePatternName.LEAF))

        return result

    def __repr__(self) -> str:
        return f"SiteDesign(Edge device: {self.num_edge_device}, Core device: {self.num_core_device}, Leaf device: {self.num_leaf_device})"


NETWORKS_SUPERNET = IPv4Network("10.0.0.0/8")
NETWORKS_SUPERNET_IPV6 = IPv6Network("2001:DB8::/100")
MANAGEMENT_NETWORKS = IPv4Network("172.16.0.0/16")

# Here with current logic we allocate 3 /29 per edge device
# We have max 10 edges on a single site, max 200 sites
# 3*10*200 = 6000 -> we need to be able to fit 6000 /29
# Thus we need a /16
NETWORKS_POOL_EXTERNAL_SUPERNET = IPv4Network("203.111.0.0/16")

ACTIVE_STATUS = "active"
BACKBONE_ROLE = "backbone"


def site_generator(nbr_site: int = 2) -> list[Site]:
    """Generate a list of site names by iterating over the list of SITES defined above and by increasing the id.

    site_names_generator(nbr_site=5)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1"]

    site_names_generator(nbr_site=12)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1", "iad1", "bkk1", "sfo1", "iah1", "mco1", "atl2", "ord2"]
    """

    sites: list[Site] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        sites.extend(
            [
                Site(name=f"{site.name}{idx}", country=site.country, city=site.city, contact=site.contact)
                for site in SITES[:nbr_this_loop]
            ]
        )

    return sites


INTERFACE_MGMT_NAME = {
    "7280R3": "Management0",
    "7010TX-48": "Management0",
    "ASR1002-HX": "Management0",
    "MX204": "MGMT",
}


LAG_INTERFACE_L2 = {
    "7280R3": [{"name": "port-channel1", "lacp": "Active", "members": ["Ethernet11", "Ethernet12"]}],
    "7010TX-48": [
        {
            "name": "port-channel1",
            "description": "MLAG peer link",
            "lacp": "Active",
            "members": ["Ethernet1", "Ethernet2"],
        },
        {
            "name": "port-channel2",
            "description": "MLAG to Server",
            "lacp": "Active",
            "members": ["Ethernet5", "Ethernet6"],
        },
    ],
}

INTERFACE_L3_ROLES_MAPPING = {
    "edge": [
        "peer",
        "peer",
        "backbone",
        "backbone",
        "upstream",
        "upstream",
        "spare",
        "spare",
        "peering",
        "spare",
        "spare",
        "spare",
    ],
    "core": [
        "backbone",
        "backbone",
        "backbone",
        "spare",
    ],
    "leaf": [],
}

INTERFACE_L2_ROLES_MAPPING = {
    "leaf": [
        "peer",
        "peer",
    ],
}

LAG_INTERFACE_L2_ROLES_MAPPING: dict[str, dict[str, str]] = {
    "leaf": {"port-channel1": "peer", "port-channel2": "server"}
}

INTERFACE_L2_MODE_MAPPING = {"peer": "Trunk (ALL)"}

MLAG_DOMAINS = {"leaf": {"domain_id": 1, "peer_interfaces": ["port-channel1", "port-channel1"]}}

MLAG_INTERFACE_L2 = {
    "leaf": [
        {
            "mlag_id": 2,
            "mlag_domain": 1,
            "members": ["port-channel2", "port-channel2"],
        }
    ]
}

TAGS = ["blue", "green", "red"]

ORGANIZATIONS = (
    Organization(name="Arelion", type="provider"),
    Organization(name="Colt Technology Services", type="provider"),
    Organization(name="Verizon Business", type="provider"),
    Organization(name="GTT Communications", type="provider"),
    Organization(name="Hurricane Electric", type="provider"),
    Organization(name="Lumen", type="provider"),
    Organization(name="Zayo", type="provider"),
    Organization(name="Equinix", type="provider"),
    Organization(name="Interxion", type="provider"),
    Organization(name="PCCW Global", type="provider"),
    Organization(name="Orange S.A", type="provider"),
    Organization(name="Tata Communications", type="provider"),
    Organization(name="Sprint", type="provider"),
    Organization(name="NTT America", type="provider"),
    Organization(name="Cogent Communications", type="provider"),
    Organization(name="Comcast Cable Communication", type="provider"),
    Organization(name="Telecom Italia Sparkle", type="provider"),
    Organization(name="AT&T Services", type="provider"),
    Organization(name="Duff", type="tenant"),
    Organization(name="Juniper", type="manufacturer"),
    Organization(name="Cisco", type="manufacturer"),
    Organization(name="Arista", type="manufacturer"),
)

ASNS = (
    Asn(asn=1299, organization="Arelion"),
    Asn(asn=64496, organization="Duff"),
    Asn(asn=8220, organization="Colt Technology Services"),
    Asn(asn=701, organization="Verizon Business"),
    Asn(asn=3257, organization="GTT Communications"),
    Asn(asn=6939, organization="Hurricane Electric"),
    Asn(asn=3356, organization="Lumen"),
    Asn(asn=6461, organization="Zayo"),
    Asn(asn=24115, organization="Equinix"),
    Asn(asn=20710, organization="Interxion"),
    Asn(asn=3491, organization="PCCW Global"),
    Asn(asn=5511, organization="Orange S.A"),
    Asn(asn=6453, organization="Tata Communications"),
    Asn(asn=1239, organization="Sprint"),
    Asn(asn=2914, organization="NTT America"),
    Asn(asn=174, organization="Cogent Communications"),
    Asn(asn=7922, organization="Comcast Cable Communication"),
    Asn(asn=6762, organization="Telecom Italia Sparkle"),
    Asn(asn=7018, organization="AT&T Services"),
)

INTERFACE_OBJS: dict[str, list[InfraInterfaceL3]] = defaultdict(list)

GLOBAL_PERMISSIONS = (
    GlobalPermission(action="edit_default_branch", decision=6),
    GlobalPermission(action="merge_branch", decision=6),
    GlobalPermission(action="merge_proposed_change", decision=6),
    GlobalPermission(action="manage_schema", decision=6),
    GlobalPermission(action="manage_accounts", decision=6),
    GlobalPermission(action="manage_permissions", decision=6),
    GlobalPermission(action="manage_repositories", decision=6),
)

OBJECT_PERMISSIONS = {
    "deny_any": ObjectPermission(namespace="*", name="*", action="any", decision=1),
    "allow_any": ObjectPermission(namespace="*", name="*", action="any", decision=6),
    "allow_branches": ObjectPermission(namespace="*", name="*", action="any", decision=4),
    "view_any": ObjectPermission(namespace="*", name="*", action="view", decision=6),
}

ACCOUNT_ROLES = (
    AccountRole(name="Administrator", global_permissions="__all__", object_permissions=["allow_any"]),
    AccountRole(name="Global read-only", object_permissions=["deny_any", "view_any"]),
    AccountRole(
        name="Global read-write",
        global_permissions=["edit_default_branch", "merge_branch", "merge_proposed_change"],
        object_permissions=["allow_any"],
    ),
    AccountRole(name="Own branches read-write", object_permissions=["allow_branches"]),
)

ACCOUNTS = (
    Account(name="pop-builder", label="pop-builder", account_type="Script", password="Password123"),
    Account(name="crm-sync", label="CRM Synchronization", account_type="Script", password="Password123"),
    Account(name="jbauer", label="Jack Bauer", account_type="User", password="Password123"),
    Account(name="cobrian", label="Chloe O'Brian", account_type="User", password="Password123"),
    Account(name="dpalmer", label="David Palmer", account_type="User", password="Password123"),
    Account(name="sudo", label="Sue Dough", password="Password123", account_type="User"),
    Account(name="elawson", label="Emily Lawson", password="Password123", account_type="User"),
    Account(name="jthompson", label="Jacob Thompson", password="Password123", account_type="User"),
    Account(name="shernandez", label="Sofia Hernandez", password="Password123", account_type="User"),
    Account(name="rpatel", label="Ryan Patel", password="Password123", account_type="User"),
    Account(name="ocarter", label="Olivia Carter", password="Password123", account_type="User"),
)

ACCOUNT_GROUPS = {
    "administrators": AccountGroup(
        name="Administrators", roles=["Administrator"], members=["sudo", "pop-builder", "crm-sync"]
    ),
    "ops-team": AccountGroup(
        name="Operations Team", roles=["Global read-only"], members=["jbauer", "elawson", "jthompson"]
    ),
    "eng-team": AccountGroup(
        name="Engineering Team", roles=["Global read-write"], members=["cobrian", "shernandez", "rpatel"]
    ),
    "arch-team": AccountGroup(
        name="Architecture Team", roles=["Own branches read-write"], members=["dpalmer", "ocarter"]
    ),
}

GROUPS = (
    Group(name="edge_router", label="Edge Router"),
    Group(name="core_router", label="Core Router"),
    # Group(name="leaf_switch", label="Leaf Switch"),
    Group(name="cisco_devices", label="Cisco Devices"),
    Group(name="arista_devices", label="Arista Devices"),
    # Group(name="juniper_devices", label="Juniper Devices"),
    Group(name="upstream_interfaces", label="Upstream Interfaces"),
    Group(name="backbone_interfaces", label="Backbone Interfaces"),
    Group(name="maintenance_circuits", label="Circuits in Maintenance"),
    Group(name="provisioning_circuits", label="Circuits in Provisioning"),
    Group(name="backbone_services", label="Backbone Services"),
)

BGP_PEER_GROUPS = (
    BgpPeerGroup(
        name="POP_INTERNAL",
        import_policies="IMPORT_INTRA_POP",
        export_policies="EXPORT_INTRA_POP",
        local_as="Duff",
        remote_as="Duff",
    ),
    BgpPeerGroup(
        name="POP_GLOBAL",
        import_policies="IMPORT_POP_GLOBAL",
        export_policies="EXPORT_POP_GLOBLA",
        local_as="Duff",
        remote_as=None,
    ),
    BgpPeerGroup(
        name="UPSTREAM_DEFAULT",
        import_policies="IMPORT_UPSTREAM",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as=None,
    ),
    BgpPeerGroup(
        name="UPSTREAM_ARELION",
        import_policies="IMPORT_UPSTREAM",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as="Arelion",
    ),
    BgpPeerGroup(
        name="IX_DEFAULT",
        import_policies="IMPORT_IX",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as=None,
    ),
)

INTERFACE_PROFILES = (
    InterfaceProfile(name="upstream_profile", mtu=1515, kind="InfraInterfaceL3"),
    InterfaceProfile(name="backbone_profile", mtu=9216, kind="InfraInterfaceL3"),
)

VLANS = (
    Vlan(id=200, role="server"),
    Vlan(id=400, role="management"),
)


async def find_and_connect_interfaces(
    client: InfrahubClient,
    batch: InfrahubBatch,
    log: logging.Logger,
    interface_kind: InfraInterfaceL2 | InfraInterfaceL3,
    first_device_name: str,
    first_interface_name: str,
    second_device_name: str,
    second_interface_name: str,
) -> None:
    # Connecting first interface to second interface
    first_interface = client.store.get(kind=interface_kind, key=first_interface_name)
    second_interface = client.store.get(kind=interface_kind, key=second_interface_name)

    first_interface.description.value = f"Connected to {second_device_name}::{second_interface.name.value}"
    first_interface.connected_endpoint = second_interface
    batch.add(task=first_interface.save, node=first_interface)

    # Adjust description on second interface
    second_interface.description.value = f"Connected to {first_device_name}::{first_interface.name.value}"
    batch.add(task=second_interface.save, node=second_interface)

    log.info(
        f" - Connected '{first_device_name}::{first_interface_name}' <> '{second_device_name}::{second_interface_name}'"
    )


# async def apply_interface_profiles(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
#     # ------------------------------------------
#     # Add profile on interfaces upstream/backbone
#     # ------------------------------------------
#     log.info("Starting to apply profiles to interfaces")
#     upstream_interfaces = await client.filters(branch=branch, kind=InfraInterfaceL3, role__value="upstream")
#     backbone_interfaces = await client.filters(branch=branch, kind=InfraInterfaceL3, role__value="backbone")
#     upstream_profile = client.store.get(key="upstream_profile", kind="ProfileInfraInterfaceL3", )
#     backbone_profile = client.store.get(key="backbone_profile", kind="ProfileInfraInterfaceL3", )

#     batch = await client.create_batch()
#     for interface in upstream_interfaces:
#         batch.add(
#             task=interface.add_relationships,
#             node=interface,
#             relation_to_update="profiles",
#             related_nodes=[upstream_profile.id],
#         )

#     for interface in backbone_interfaces:
#         batch.add(
#             task=interface.add_relationships,
#             node=interface,
#             relation_to_update="profiles",
#             related_nodes=[backbone_profile.id],
#         )

#     async for _, response in batch.execute():
#         log.debug(f"{response} - Creation Completed")

#     log.info("Done applying profiles to interfaces")


async def apply_interface_profiles_and_groups(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    """
    Apply profiles to upstream/backbone L3 interfaces and add them to their respective groups.
    """
    log.info("Applying profiles to interfaces and update interface groups")

    # Fetch upstream and backbone interfaces.
    upstream_interfaces = await client.filters(
        branch=branch,
        kind=InfraInterfaceL3,
        role__value="upstream",
        order=Order(disable=True),
    )
    backbone_interfaces = await client.filters(
        branch=branch,
        kind=InfraInterfaceL3,
        role__value="backbone",
        order=Order(disable=True),
    )

    # Retrieve profiles from the store.
    upstream_profile = client.store.get(
        key="upstream_profile",
        kind="ProfileInfraInterfaceL3",
    )
    backbone_profile = client.store.get(
        key="backbone_profile",
        kind="ProfileInfraInterfaceL3",
    )

    # Apply profiles using batch processing.
    batch = await client.create_batch()
    for interface in upstream_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[upstream_profile.id],
        )
    for interface in backbone_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[backbone_profile.id],
        )
    async for _, response in batch.execute():
        log.debug(f"{response} - Profile applied")
    log.info("Completed applying profiles to interfaces")

    # Update interface groups.
    if upstream_interfaces:
        group_upstream_interfaces = await client.get(
            kind=CoreStandardGroup,
            name__value="upstream_interfaces",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        upstream_interface_ids = [interface.id for interface in upstream_interfaces]
        await group_upstream_interfaces.add_relationships(
            relation_to_update="members", related_nodes=upstream_interface_ids
        )
    if backbone_interfaces:
        group_backbone_interfaces = await client.get(
            kind=CoreStandardGroup,
            name__value="backbone_interfaces",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        backbone_interface_ids = [interface.id for interface in backbone_interfaces]
        await group_backbone_interfaces.add_relationships(
            relation_to_update="members", related_nodes=backbone_interface_ids
        )
    log.info("Completed updating interface groups")


async def apply_devices_groups(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    """
    Fetch devices from Infrahub, group them based on their role and manufacturer,
    and update the corresponding device groups.
    """
    log.info("Adding devices to groups")

    devices = await client.filters(
        branch=branch,
        kind="InfraDevice",
        include=["name", "role", "platform"],
        prefetch_relationships=True,
        order=Order(disable=True),
    )

    # Initialize lists for grouping by role.
    group_core_router_members: list[str] = []
    group_edge_router_members: list[str] = []
    group_leaf_switch_members: list[str] = []

    # Initialize lists for grouping by manufacturer/platform.
    group_arista_devices_members: list[str] = []
    group_cisco_devices_members: list[str] = []
    group_juniper_devices_members: list[str] = []

    # Build lists of device names to add to groups.
    for device in devices:
        device_role = device.role.value
        if "edge" in device_role:
            group_edge_router_members.append(device.id)
        elif "core" in device_role:
            group_core_router_members.append(device.id)
        # elif "leaf" in device_role:
        #     group_leaf_switch_members.append(device.id)

        if "Arista" in device.platform.peer.name.value:
            group_arista_devices_members.append(device.id)
        elif "Cisco" in device.platform.peer.name.value:
            group_cisco_devices_members.append(device.id)
        # elif "Juniper" in device.platform.peer.name.value:
        #     group_juniper_devices_members.append(device.id)

    # Update device groups.
    log.info("Updating device groups")
    if group_edge_router_members:
        group_edge_router = await client.get(
            kind=CoreStandardGroup,
            name__value="edge_router",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_edge_router.add_relationships(relation_to_update="members", related_nodes=group_edge_router_members)
    if group_core_router_members:
        group_core_router = await client.get(
            kind=CoreStandardGroup,
            name__value="core_router",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_core_router.add_relationships(relation_to_update="members", related_nodes=group_core_router_members)
    if group_leaf_switch_members:
        group_leaf_switch = await client.get(
            kind=CoreStandardGroup,
            name__value="leaf_switch",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_leaf_switch.add_relationships(relation_to_update="members", related_nodes=group_leaf_switch_members)
    if group_arista_devices_members:
        group_arista_devices = await client.get(
            kind=CoreStandardGroup,
            name__value="arista_devices",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_arista_devices.add_relationships(
            relation_to_update="members", related_nodes=group_arista_devices_members
        )
    if group_cisco_devices_members:
        group_cisco_devices = await client.get(
            kind=CoreStandardGroup,
            name__value="cisco_devices",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_cisco_devices.add_relationships(
            relation_to_update="members", related_nodes=group_cisco_devices_members
        )
    if group_juniper_devices_members:
        group_juniper_devices = await client.get(
            kind=CoreStandardGroup,
            name__value="juniper_devices",
            branch=branch,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_juniper_devices.add_relationships(
            relation_to_update="members", related_nodes=group_juniper_devices_members
        )
    log.info("Devices have been added to groups")


async def create_backbone_connectivity(
    client: InfrahubClient, log: logging.Logger, branch: str, num_sites: int
) -> None:
    # --------------------------------------------------
    # CREATE Backbone Links & Circuits
    # --------------------------------------------------
    log.info("Creating Backbone Links & Circuits")
    account_pop = client.store.get(
        "pop-builder",
        kind=CoreAccount,
    )
    interconnection_pool = client.store.get(
        "Interconnections pool",
        kind=CoreIPPrefixPool,
    )

    p2p_networks: list[P2pNetwork] = []

    if num_sites > 1:
        p2p_networks.append(P2pNetwork(site1="atl1", site2="ord1", edge=1, circuit="DUFF-1543451"))
        p2p_networks.append(P2pNetwork(site1="atl1", site2="ord1", edge=2, circuit="DUFF-8263953"))
    if num_sites > 2:
        p2p_networks.append(P2pNetwork(site1="atl1", site2="jfk1", edge=1, circuit="DUFF-6535773"))
        p2p_networks.append(P2pNetwork(site1="atl1", site2="jfk1", edge=2, circuit="DUFF-7324064"))
        p2p_networks.append(P2pNetwork(site1="jfk1", site2="ord1", edge=1, circuit="DUFF-5826854"))
        p2p_networks.append(P2pNetwork(site1="jfk1", site2="ord1", edge=2, circuit="DUFF-4867430"))

    for network in p2p_networks:
        network.pool = await client.allocate_next_ip_prefix(
            resource_pool=interconnection_pool, kind=IpamIPPrefix, branch=branch, identifier=network.identifier
        )

    log.info("- Done allocating addresses")

    circuit_batch = await client.create_batch()
    endpoint_batch = await client.create_batch()
    interface_ip_batch = await client.create_batch()
    for backbone_link in p2p_networks:
        # intf1 = INTERFACE_OBJS[backbone_link.site1_device].pop(0)
        # intf2 = INTERFACE_OBJS[backbone_link.site2_device].pop(0)
        intf_site1 = INTERFACE_OBJS[backbone_link.site1_device].pop(0)
        intf_site1_obj = await client.get(id=intf_site1.id, include=["device"], kind=InfraInterfaceL3)
        intf_site2 = INTERFACE_OBJS[backbone_link.site2_device].pop(0)
        intf_site2_obj = await client.get(id=intf_site2.id, include=["device"], kind=InfraInterfaceL3)

        backbone_link_ips = backbone_link.get_pool().prefix.value.hosts()

        provider = client.store.get(kind=OrganizationProvider, key=backbone_link.provider_name)
        vendor_id = f"{backbone_link.provider_name}-{UUIDT().short()}"
        bkb_circuit = await client.create(
            branch=branch,
            kind=InfraCircuit,
            description=f"BKB: {backbone_link.site1} <-> {backbone_link.site2}",
            circuit_id=backbone_link.circuit,
            vendor_id=vendor_id.upper(),
            provider=provider,
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        circuit_batch.add(task=bkb_circuit.save, node=bkb_circuit)

        # Create Circuit Endpoints
        endpoint1 = await client.create(
            branch=branch,
            kind=InfraCircuitEndpoint,
            description=f"Endpoint {backbone_link.circuit} to {backbone_link.site1_device}",
            site=backbone_link.site1,
            circuit=bkb_circuit,
            connected_endpoint=intf_site1,
        )
        endpoint_batch.add(task=endpoint1.save, node=endpoint1)

        endpoint2 = await client.create(
            branch=branch,
            kind=InfraCircuitEndpoint,
            description=f"Endpoint {backbone_link.circuit} to {backbone_link.site2_device}",
            site=backbone_link.site2,
            circuit=bkb_circuit,
            connected_endpoint=intf_site2,
        )
        endpoint_batch.add(task=endpoint2.save, node=endpoint2)

        # Create IP Address
        intf_site1_address = f"{str(next(backbone_link_ips))}/31"
        intf_site2_address = f"{str(next(backbone_link_ips))}/31"
        intf_site1_identifier = f"{intf_site1.name.value.lower()}.{intf_site1_obj.device.peer.name.value}"
        intf_site2_identifier = f"{intf_site2.name.value.lower()}.{intf_site2_obj.device.peer.name.value}"
        intf_site1_ip = await client.create(
            branch=branch,
            kind=IpamIPAddress,
            interface={"id": intf_site1.id, "source": account_pop.id},
            address={"value": intf_site1_address, "source": account_pop.id},
            description={"value": intf_site1_identifier, "source": account_pop.id},
        )
        interface_ip_batch.add(task=intf_site1_ip.save, node=intf_site1_ip)

        intf_site2_ip = await client.create(
            branch=branch,
            kind=IpamIPAddress,
            interface={"id": intf_site2.id, "source": account_pop.id},
            address={"value": intf_site2_address, "source": account_pop.id},
            description={"value": intf_site2_identifier, "source": account_pop.id},
        )
        interface_ip_batch.add(task=intf_site2_ip.save, node=intf_site2_ip)

        # Update Interface
        intf_site1_obj.description.value = (
            f"Backbone: Connected to {backbone_link.site2_device} via {backbone_link.circuit}"
        )
        await intf_site1_obj.save()

        intf_site2_obj.description.value = (
            f"Backbone: Connected to {backbone_link.site1_device} via {backbone_link.circuit}"
        )
        await intf_site2_obj.save()
        bb_service = await client.create(
            kind="InfraBackBoneService",
            name=f"BKB: {backbone_link.site1} <-> {backbone_link.site2}",
            circuit_id=backbone_link.circuit,
            internal_circuit_id=vendor_id.upper(),
            provider=provider,
            site_a=backbone_link.site1,
            site_b=backbone_link.site2,
        )
        await bb_service.save(allow_upsert=True)

        log.debug(
            f" - Connected '{backbone_link.site1_device}::{intf_site1.name.value}' <> '{backbone_link.site2_device}::{intf_site2.name.value}'"
        )
    async for node, _ in circuit_batch.execute():
        log.info(f"Created {node.get_kind()} - {node.get_human_friendly_id()}")
    async for node, _ in endpoint_batch.execute():
        log.info(f"Created {node.get_kind()} - ['{node.id}']")
    async for node, _ in interface_ip_batch.execute():
        log.info(f"Created {node.get_kind()} - {node.get_human_friendly_id()}")


async def create_bgp_mesh(client: InfrahubClient, log: logging.Logger, branch: str, sites: list[Site]) -> None:
    # --------------------------------------------------
    # CREATE Full Mesh iBGP SESSION between all the Edge devices
    # --------------------------------------------------
    log.info("Creating Full Mesh iBGP SESSION between all the Edge devices")
    batch = await client.create_batch()
    num_sites = len(sites)
    internal_as = client.store.get(kind=InfraAutonomousSystem, key="Duff")

    for site1 in sites:
        for site2 in sites:
            if site1 == site2:
                continue

            for idx1 in range(1, min(3, num_sites)):
                for idx2 in range(1, min(3, num_sites)):
                    device1 = f"{site1.name}-edge{idx1}"
                    device2 = f"{site2.name}-edge{idx2}"

                    loopback1 = client.store.get(
                        key=f"{device1}-loopback-ip",
                        kind=IpamIPAddress,
                    )
                    loopback2 = client.store.get(
                        key=f"{device2}-loopback-ip",
                        kind=IpamIPAddress,
                    )

                    peer_group_name = "POP_GLOBAL"

                    obj = await client.create(
                        branch=branch,
                        kind=InfraBGPSession,
                        type="INTERNAL",
                        local_as=internal_as.id,
                        local_ip=loopback1.id,
                        remote_as=internal_as.id,
                        remote_ip=loopback2.id,
                        peer_group=client.store.get(
                            kind=InfraBGPPeerGroup,
                            key=peer_group_name,
                        ).id,
                        device=client.store.get(
                            kind=InfraDevice,
                            key=device1,
                        ).id,
                        status=ACTIVE_STATUS,
                        role=BACKBONE_ROLE,
                    )
                    batch.add(task=obj.save, node=obj)

    async for node, _ in batch.execute():
        if node._schema.default_filter:
            accessor = f"{node._schema.default_filter.split('__')[0]}"
            log.info(f"{node.get_kind()} {getattr(node, accessor).value} - Creation Completed")
        else:
            log.info(f"{node} - Creation Completed")


async def generate_site_vlans(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    site: Site,
    site_id: int,
) -> None:
    account_pop = client.store.get(
        "pop-builder",
        kind=CoreAccount,
    )
    group_eng = client.store.get(
        "eng-team",
        kind=CoreAccountGroup,
    )
    group_ops = client.store.get(
        "ops-team",
        kind=CoreAccountGroup,
    )

    vlan_batch = await client.create_batch()
    for vlan in VLANS:
        vlan_name = f"{site.name}_{vlan.role}"
        obj = await client.create(
            branch=branch,
            kind=InfraVLAN,
            site={"id": site_id, "source": account_pop.id, "is_protected": True},
            name={"value": vlan_name, "is_protected": True, "source": account_pop.id},
            vlan_id={"value": vlan.id, "is_protected": True, "owner": group_eng.id, "source": account_pop.id},
            status={"value": ACTIVE_STATUS, "owner": group_ops.id},
            role={"value": vlan.role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
        )
        vlan_batch.add(task=obj.save, node=obj)
        client.store.set(key=vlan_name, node=obj)

    async for node, _ in vlan_batch.execute():
        log.debug(f"Created {node.get_kind()} - {node.name.value}")


async def generate_site_mlag_domain(client: InfrahubClient, log: logging.Logger, branch: str, site: Site) -> None:  # noqa: ARG001
    # --------------------------------------------------
    # Set up MLAG domains
    # --------------------------------------------------
    for role, domain in MLAG_DOMAINS.items():
        devices = [
            client.store.get(kind=InfraDevice, key=f"{site.name}-{role}1"),
            client.store.get(kind=InfraDevice, key=f"{site.name}-{role}2"),
        ]
        name = f"{site.name}-{role}-12"

        peer_interfaces = [
            client.store.get(
                kind=InfraLagInterfaceL2, key=f"{device_obj.name.value}-lagl2-{domain['peer_interfaces'][idx]}"
            )  # type: ignore[index]
            for idx, device_obj in enumerate(devices)
        ]

        mlag_domain = await client.create(
            kind=InfraMlagDomain,
            name=name,
            domain_id=domain["domain_id"],
            devices=devices,
            peer_interfaces=peer_interfaces,
        )

        await mlag_domain.save()
        client.store.set(key=f"mlag-domain-{name}", node=mlag_domain)

    # --------------------------------------------------
    # Set up MLAG Interfaces
    # --------------------------------------------------
    for role, mlags in MLAG_INTERFACE_L2.items():
        devices = [
            client.store.get(kind=InfraDevice, key=f"{site.name}-{role}1"),
            client.store.get(kind=InfraDevice, key=f"{site.name}-{role}2"),
        ]

        for mlag in mlags:
            members = [
                client.store.get(kind=InfraLagInterfaceL2, key=f"{device_obj.name.value}-lagl2-{mlag['members'][idx]}")  # type: ignore[index]
                for idx, device_obj in enumerate(devices)
            ]
            mlag_domain = client.store.get(kind=InfraMlagDomain, key=f"mlag-domain-{site.name}-{role}-12")

            mlag_interface = await client.create(
                kind=InfraMlagInterfaceL2, mlag_domain=mlag_domain, mlag_id=mlag["mlag_id"], members=members
            )

            await mlag_interface.save()


async def generate_site(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    site: Site,
    interconnection_pool: CoreNode,
    loopback_pool: CoreNode,
    management_pool: CoreNode,
    external_pool: CoreNode,
    site_design: SiteDesign,
) -> str:
    group_eng = client.store.get("eng-team", kind=CoreAccountGroup)
    group_ops = client.store.get("ops-team", kind=CoreAccountGroup)
    account_pop = client.store.get("pop-builder", kind=CoreAccount)
    account_crm = client.store.get("crm-sync", kind=CoreAccount)
    internal_as = client.store.get("Duff", kind=InfraAutonomousSystem)

    country = client.store.get(kind=LocationCountry, key=site.country)
    # --------------------------------------------------
    # Create the Site
    # --------------------------------------------------
    site_obj = await client.create(
        branch=branch,
        kind=LocationSite,
        name={"value": site.name, "is_protected": True, "source": account_crm.id},
        contact={"value": site.contact, "is_protected": True, "source": account_crm.id},
        city={"value": site.city, "is_protected": True, "source": account_crm.id},
        parent=country,
    )
    await site_obj.save()
    log.info(f"- Created {site_obj.get_kind()} - {site.name}")

    await generate_site_vlans(client=client, log=log, branch=branch, site=site, site_id=site_obj.id)

    # --------------------------------------------------
    # Create the site specific IP prefixes
    # --------------------------------------------------
    # TODO: Refactor that part for the sake of readability
    # Here we dispatch to every p2p a /31 prefixe
    # Between two edges we have 2 p2p connections so 2 prefixes
    # So far we connect edge1<->edge2 then edge3<->edge4 ...
    peer_networks: list[IpamIPPrefix] = []
    peer_network_hosts = {
        # 0: {0: peer_networks[0].prefix.value.hosts(), 1: peer_networks[1].prefix.value.hosts()},
        # ^ Device id                                   ^ interface id
    }

    # Here we need as much prefix as we have edge device
    for _ in range(site_design.num_edge_device):
        peer_networks.append(
            await client.allocate_next_ip_prefix(resource_pool=interconnection_pool, kind=IpamIPPrefix, branch=branch)
        )

    # Then we prepare all ips for all interfaces
    # TODO: Refactor that part for the sake of readability
    for i in range(1, site_design.num_edge_device, 2):
        peer_network_hosts[i] = {
            0: peer_networks[i - 1].prefix.value.hosts(),
            1: peer_networks[i].prefix.value.hosts(),
        }
        peer_network_hosts[i + 1] = {
            0: peer_networks[i - 1].prefix.value.hosts(),
            1: peer_networks[i].prefix.value.hosts(),
        }

    # group_core_router_members: list[str] = []
    # group_edge_router_members: list[str] = []
    # group_cisco_devices_members: list[str] = []
    # group_arista_devices_members: list[str] = []
    # group_upstream_interfaces_members = []
    # group_backbone_interfaces_members = []

    # --------------------------------------------------
    # Create devices
    # --------------------------------------------------
    # Craft the list of devices
    devices: list[Device] = site_design.implement()

    device_batch = await client.create_batch()
    for device in devices:
        device_name = f"{site.name}-{device.name}"
        platform_id = client.store.get(kind=InfraPlatform, key=device.platform).id

        obj = await client.create(
            branch=branch,
            kind=InfraDevice,
            site={"id": site_obj.id, "source": account_pop.id, "is_protected": True},
            name={"value": device_name, "source": account_pop.id, "is_protected": True},
            status={"value": device.status, "owner": group_ops.id},
            type={"value": device.type, "source": account_pop.id},
            role={"value": device.role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            asn={"id": internal_as.id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            tags=[
                client.store.get(
                    kind=BuiltinTag,
                    key=tag_name,
                ).id
                for tag_name in device.tags
            ],
            platform={"id": platform_id, "source": account_pop.id, "is_protected": True},
        )
        device_batch.add(task=obj.save, node=obj)
        client.store.set(node=obj)

    async for node, _ in device_batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.get_human_friendly_id()}")

    # --------------------------------------------------
    # Create interfaces for each device
    # --------------------------------------------------
    log.info(f"[{site.name}] Creating Interfaces, IPs, Circuits & BGP Sessions")
    for device in devices:
        device_name = f"{site.name}-{device.name}"
        obj = client.store.get(key=device_name, kind=InfraDevice)

        # Loopback Interface
        intf = await client.create(
            branch=branch,
            kind=InfraInterfaceL3,
            device={"id": obj.id, "is_protected": True},
            name={"value": "Loopback0", "source": account_pop.id, "is_protected": True},
            enabled=True,
            status=ACTIVE_STATUS,
            role="loopback",
            speed=1000,
        )
        await intf.save()

        ip = await client.allocate_next_ip_address(
            resource_pool=loopback_pool, identifier=device_name, data={"interface": intf.id}, branch=branch
        )
        client.store.set(key=f"{device_name}-loopback-ip", node=ip)

        # Management Interface
        intf = await client.create(
            branch=branch,
            kind=InfraInterfaceL3,
            device={"id": obj.id, "is_protected": True},
            name={"value": INTERFACE_MGMT_NAME[device.type], "source": account_pop.id},
            enabled={"value": True, "owner": group_eng.id},
            status={"value": ACTIVE_STATUS, "owner": group_eng.id},
            role={"value": "management", "source": account_pop.id, "is_protected": True},
            speed=1000,
        )
        await intf.save()
        management_ip = await client.allocate_next_ip_address(
            resource_pool=management_pool, identifier=device_name, data={"interface": intf.id}, branch=branch
        )
        management_ip = cast("IpamIPAddress", management_ip)

        # set the IP address of the device to the management interface IP address
        obj.primary_address = management_ip  # type: ignore[assignment]
        await obj.save()

        # L3 Interfaces
        l3_interface_batch = await client.create_batch()
        address_batch = await client.create_batch()
        circuit_batch = await client.create_batch()
        cable_batch = await client.create_batch()
        endpoint_batch = await client.create_batch()
        bgp_session_batch = await client.create_batch()

        for intf_idx, intf_name in enumerate(device.l3_interface_names):
            intf_role = INTERFACE_L3_ROLES_MAPPING[device.role][intf_idx]

            intf = await client.create(
                branch=branch,
                kind=InfraInterfaceL3,
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
            )
            # Instead of immediate saving, add the interface creation to the batch.
            l3_interface_batch.add(task=intf.save, node=intf)
            # Store the interface for later reference.
            client.store.set(key=f"{device_name}-l3-{intf_idx}", node=intf)

            interface_identifier = f"{intf.name.value.lower()}.{device_name}"

            # Determine the IP address (if any) for this interface.
            address = None
            peer_address = None  # For roles that require a peer IP

            if "edge" in device.role:
                if intf_role == "backbone":
                    INTERFACE_OBJS[device_name].append(intf)

                if intf_role == "peer":
                    # TODO: Refactor that part for the sake of readability
                    address = f"{str(next(peer_network_hosts[device._idx][intf_idx]))}/31"

                if intf_role in ["upstream", "peering"]:
                    prefix_identifier = f"{intf_role}: {intf.name.value}.{device_name}"
                    subnet = await client.allocate_next_ip_prefix(
                        kind=IpamIPPrefix,
                        resource_pool=external_pool,
                        identifier=prefix_identifier,
                        data={
                            "description": {
                                "value": prefix_identifier,
                                "source": account_pop.id,
                            }
                        },
                        branch=branch,
                    )
                    subnet_hosts = subnet.prefix.value.hosts()
                    address = f"{str(next(subnet_hosts))}/29"
                    peer_address = f"{str(next(subnet_hosts))}/29"

            if address:
                ip = await client.create(
                    branch=branch,
                    kind=IpamIPAddress,
                    interface=intf,
                    address={"value": address, "source": account_pop.id},
                    description={
                        "value": interface_identifier,
                        "source": account_pop.id,
                    },
                )
                address_batch.add(task=ip.save, node=ip, allow_upsert=True)

            # Create Circuit and BGP session for upstream and peering
            if intf_role in ["upstream", "peering"]:
                circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-{intf_role}-{address}"))))[24:]
                circuit_id = f"DUFF-{circuit_id_unique}"
                upstream_providers = ["Arelion", "Colt Technology Services"]
                bgp_session = None

                if intf_role == "upstream":
                    provider_name = upstream_providers[intf_idx % 2]
                    provider = client.store.get(
                        kind=OrganizationProvider,
                        key=provider_name,
                    )

                    peer_group_name = (
                        "UPSTREAM_ARELION" if "arelion" in provider.name.value.lower() else "UPSTREAM_DEFAULT"
                    )

                    peer_ip = await client.create(
                        branch=branch,
                        kind=IpamIPAddress,
                        address=peer_address,
                    )
                    address_batch.add(task=peer_ip.save, node=peer_ip, allow_upsert=True)
                    session_description = f"external-{ip.address.value.ip}-{peer_ip.address.value.ip}"
                    bgp_session = await client.create(
                        branch=branch,
                        kind=InfraBGPSession,
                        type="EXTERNAL",
                        description=session_description,
                        local_as=internal_as.id,
                        local_ip=ip,
                        remote_as=client.store.get(kind=InfraAutonomousSystem, key=provider_name).id,
                        remote_ip=peer_ip,
                        peer_group=client.store.get(
                            key=peer_group_name,
                            kind=InfraBGPPeerGroup,
                        ).id,
                        device=client.store.get(
                            key=device_name,
                            kind=InfraDevice,
                        ).id,
                        status=ACTIVE_STATUS,
                        role=intf_role,
                    )
                    bgp_session_batch.add(task=bgp_session.save, node=bgp_session)

                elif intf_role == "peering":
                    provider_name = "Equinix"

                    # await circuit.add_relationships(relation_to_update="bgp_sessions", related_nodes=[bgp_session.id])
                    # log.debug(
                    #     f" - Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                    # )

                circuit_data = {
                    "circuit_id": circuit_id,
                    "vendor_id": f"{provider_name.upper()}-{UUIDT().short()}",
                    "provider": provider.id,
                    "status": {"value": ACTIVE_STATUS, "owner": group_ops.id},
                    "role": {
                        "value": intf_role,
                        "source": account_pop.id,
                        "owner": group_eng.id,
                    },
                }
                if bgp_session:
                    circuit_data["bgp_sessions"] = [bgp_session]

                circuit = await client.create(branch=branch, kind=InfraCircuit, data=circuit_data)
                circuit_batch.add(task=circuit.save, node=circuit)

                endpoint1 = await client.create(
                    branch=branch,
                    kind=InfraCircuitEndpoint,
                    site=site_obj,
                    circuit=circuit,
                    connected_endpoint=intf,
                )
                endpoint_batch.add(task=endpoint1.save, node=endpoint1)

                intf.description.value = f"Connected to {provider_name} via {circuit_id}"

        async for node, _ in l3_interface_batch.execute():
            log.info(f" - Created {node.get_kind()} - ['{node.name.value}']")
        async for node, _ in address_batch.execute():
            log.info(f" - Created {node.get_kind()} - ['{node.address.value}']")
        async for node, _ in bgp_session_batch.execute():
            log.info(f" - Created {node.get_kind()} - {node.get_human_friendly_id()}")
        async for node, _ in circuit_batch.execute():
            log.info(f" - Created {node.get_kind()} - {node.get_human_friendly_id()}")
        async for node, _ in cable_batch.execute():
            log.info(f" - Created {node.get_kind()} - {node.get_human_friendly_id()}")
        async for node, _ in endpoint_batch.execute():
            log.info(f" - Created {node.get_kind()} - ['{node.id}']")

        # L2 Interfaces
        l2_interface_batch = await client.create_batch()

        for intf_idx, intf_name in enumerate(device.l2_interface_names):
            try:
                intf_role = INTERFACE_L2_ROLES_MAPPING.get(device.role, [])[intf_idx]
            except IndexError:
                intf_role = "server"

            l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

            untagged_vlan = None
            if l2_mode == "Access":
                untagged_vlan = client.store.get(kind=InfraVLAN, key=f"{site.name}_server")

            intf = await client.create(
                branch=branch,
                kind=InfraInterfaceL2,
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
                l2_mode=l2_mode,
                untagged_vlan=untagged_vlan,
            )

            l2_interface_batch.add(task=intf.save, node=intf)
            client.store.set(key=f"{device_name}-l2-{intf_name}", node=intf)

        async for node, _ in l2_interface_batch.execute():
            log.debug(f"- Created {node.get_kind()} - {node.name.value}")

        for lag_intf in LAG_INTERFACE_L2.get(device.type, []):
            try:
                intf_role = LAG_INTERFACE_L2_ROLES_MAPPING[device.role][lag_intf["name"]]  # type: ignore[index]
            except KeyError:
                intf_role = "server"

            l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

            description = lag_intf.get("description", "")

            untagged_vlan = None
            if l2_mode == "Access":
                untagged_vlan = client.store.get(kind=InfraVLAN, key=f"{site.name}_server")

            lag = await client.create(
                branch=branch,
                kind=InfraLagInterfaceL2,
                device={"id": obj.id, "is_protected": True},
                name=lag_intf["name"],
                description=description,
                speed=10000,
                enabled=True,
                l2_mode=l2_mode,
                untagged_vlan=untagged_vlan,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
                lacp=lag_intf["lacp"],
            )

            await lag.save()

            client.store.set(key=f"{device_name}-lagl2-{lag_intf['name']}", node=lag)

            members = [
                client.store.get(
                    key=f"{device_name}-l2-{member}",
                ).id
                for member in lag_intf["members"]
            ]
            await lag.add_relationships(relation_to_update="members", related_nodes=members)

    await generate_site_mlag_domain(client=client, log=log, branch=branch, site=site)

    # Create a batch for all those connections
    batch_interface: InfrahubBatch = await client.create_batch()

    # --------------------------------------------------
    # Connect edge devices 2 by 2
    # --------------------------------------------------
    for idx in range(1, site_design.num_edge_device, 2):
        # Connecting eth 0 to eth 0
        await find_and_connect_interfaces(
            client=client,
            batch=batch_interface,
            log=log,
            interface_kind=InfraInterfaceL3,
            first_device_name=f"{site.name}-edge{idx}",
            first_interface_name=f"{site.name}-edge{idx}-l3-0",
            second_device_name=f"{site.name}-edge{idx + 1}",
            second_interface_name=f"{site.name}-edge{idx + 1}-l3-0",
        )

        # Connecting eth 1 to eth 1
        await find_and_connect_interfaces(
            client=client,
            batch=batch_interface,
            log=log,
            interface_kind=InfraInterfaceL3,
            first_device_name=f"{site.name}-edge{idx}",
            first_interface_name=f"{site.name}-edge{idx}-l3-1",
            second_device_name=f"{site.name}-edge{idx + 1}",
            second_interface_name=f"{site.name}-edge{idx + 1}-l3-1",
        )

    # --------------------------------------------------
    # Connect leaf devices 2 by 2
    # --------------------------------------------------
    for idx in range(1, site_design.num_leaf_device, 2):
        # Connecting eth 1 to eth 1
        await find_and_connect_interfaces(
            client=client,
            batch=batch_interface,
            log=log,
            interface_kind=InfraInterfaceL2,
            first_device_name=f"{site.name}-leaf{idx}",
            first_interface_name=f"{site.name}-leaf{idx}-l2-Ethernet1",
            second_device_name=f"{site.name}-leaf{idx + 1}",
            second_interface_name=f"{site.name}-leaf{idx + 1}-l2-Ethernet1",
        )

        # Connecting eth 2 to eth 2
        await find_and_connect_interfaces(
            client=client,
            batch=batch_interface,
            log=log,
            interface_kind=InfraInterfaceL2,
            first_device_name=f"{site.name}-leaf{idx}",
            first_interface_name=f"{site.name}-leaf{idx}-l2-Ethernet2",
            second_device_name=f"{site.name}-leaf{idx + 1}",
            second_interface_name=f"{site.name}-leaf{idx + 1}-l2-Ethernet2",
        )

    async for node, _ in batch_interface.execute():
        log.info(f"- Saving {node.get_kind()} - {node.name.value}")

    # --------------------------------------------------
    # Update all the group we may have touched during the site creation
    # --------------------------------------------------
    # if group_edge_router_members:
    #     group_edge_router = client.store.get(kind=CoreStandardGroup, key="edge_router")
    #     await group_edge_router.add_relationships(relation_to_update="members", related_nodes=group_edge_router_members)

    # if group_core_router_members:
    #     group_core_router = client.store.get(kind=CoreStandardGroup, key="core_router")
    #     await group_core_router.add_relationships(relation_to_update="members", related_nodes=group_core_router_members)

    # if group_cisco_devices_members:
    #     group_cisco_devices = client.store.get(kind=CoreStandardGroup, key="cisco_devices")
    #     await group_cisco_devices.add_relationships(
    #         relation_to_update="members", related_nodes=group_cisco_devices_members
    #     )

    # if group_arista_devices_members:
    #     group_arista_devices = client.store.get(kind=CoreStandardGroup, key="arista_devices")
    #     await group_arista_devices.add_relationships(
    #         relation_to_update="members", related_nodes=group_arista_devices_members
    #     )

    # if group_upstream_interfaces_members:
    #     group_upstream_interfaces = client.store.get(kind=CoreStandardGroup, key="upstream_interfaces")
    #     await group_upstream_interfaces.add_relationships(
    #         relation_to_update="members", related_nodes=group_upstream_interfaces_members
    #     )

    # if group_backbone_interfaces_members:
    #     group_backbone_interfaces = client.store.get(kind=CoreStandardGroup, key="backbone_interfaces")
    #     await group_backbone_interfaces.add_relationships(
    #         relation_to_update="members", related_nodes=group_backbone_interfaces_members
    #     )

    return site.name


async def branch_scenario_add_upstream(
    client: InfrahubClient, log: logging.Logger, site_name: str, external_pool: CoreNode
) -> None:
    """
    Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site.
    """
    log.info("Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site")
    device_name = f"{site_name}-edge1"

    new_branch_name = f"{site_name}-add-upstream"
    await client.branch.create(
        branch_name=new_branch_name, sync_with_git=False, description=f"Add a new Upstream link in {site_name}"
    )
    log.info(f"- Creating branch: {new_branch_name!r}")
    # Querying the object for now, need to pull from the store instead
    site = await client.get(branch=new_branch_name, kind=LocationSite, name__value=site_name)
    device = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device_name)
    gtt_organization = await client.get(
        branch=new_branch_name, kind=OrganizationProvider, name__value="GTT Communications"
    )

    role_spare = "spare"

    intfs = await client.filters(
        branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device.id], role__value=role_spare
    )
    intf = intfs[0]
    log.info(f" - Adding new Upstream on '{device_name}::{intf.name.value}'")

    # Allocate a new subnet and calculate new IP Addresses
    subnet = await client.allocate_next_ip_prefix(
        resource_pool=external_pool, identifier=device_name, branch=new_branch_name
    )
    subnet = cast("IpamIPPrefix", subnet)
    subnet_hosts = subnet.prefix.value.hosts()
    address = f"{str(next(subnet_hosts))}/29"
    peer_address = f"{str(next(subnet_hosts))}/29"

    peer_ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        address=peer_address,
    )
    await peer_ip.save()

    ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": intf.id},
        address={"value": address},
    )
    await ip.save()

    circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-upstream-{address}"))))[24:]
    circuit_id = f"DUFF-{circuit_id_unique}"

    circuit = await client.create(
        branch=new_branch_name,
        kind=InfraCircuit,
        circuit_id=circuit_id,
        vendor_id=f"{gtt_organization.name.value.upper()}-{UUIDT().short()}",
        provider=gtt_organization.id,
        status=ACTIVE_STATUS,
        role="upstream",
    )
    await circuit.save()
    log.info(f"  - Created {circuit.get_kind()} - {gtt_organization.name.value} [{circuit.vendor_id.value}]")

    endpoint1 = await client.create(
        branch=new_branch_name,
        kind=InfraCircuitEndpoint,
        site=site,
        circuit=circuit.id,
        connected_endpoint=intf.id,
    )
    await endpoint1.save()

    intf.description.value = f"Connected to {gtt_organization.name.value} via {circuit_id}"
    await intf.save()

    # Create BGP Session

    # Create Circuit
    # Create IP address
    # Change Role
    # Change description

    # peer_group_name = "UPSTREAM_DEFAULT"

    #     peer_as = client.store.get(kind="InfraAutonomousSystem", key=gtt_organization.name.value)
    #     bgp_session = await client.create(
    #         branch=branch,
    #         kind="InfraBGPSession",
    #         type="EXTERNAL",
    #         local_as=internal_as.id,
    #         local_ip=ip.id,
    #         remote_as=peer_as.id,
    #         remote_ip=peer_ip.id,
    #         peer_group=store.get(key=peer_group_name).id,
    #         device=store.get(key=device_name).id,
    #         status=ACTIVE_STATUS,
    #         role=store.get(kind="BuiltinRole", key=intf_role).id,
    #     )
    #     await bgp_session.save()

    #     log.info(
    #         f"Created BGP Session '{device_name}' >> '{gtt_organization.name.value}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
    #     )


async def branch_scenario_replace_ip_addresses(
    client: InfrahubClient, log: logging.Logger, site_name: str, interconnection_pool: CoreNode
) -> None:
    """
    Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site
    """
    device1_name = f"{site_name}-edge1"
    device2_name = f"{site_name}-edge2"

    new_branch_name = f"{site_name}-update-edge-ips"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Change the IP addresses between edge1 and edge2 in {site_name}",
    )
    log.info("Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site")
    log.info(f"- Creating branch: {new_branch_name!r}")

    new_peer_network = await client.allocate_next_ip_prefix(
        kind=IpamIPPrefix,
        resource_pool=interconnection_pool,
        identifier=f"{device1_name}__{device2_name}",
        branch=new_branch_name,
    )
    new_peer_network_hosts = new_peer_network.prefix.value.hosts()

    device1 = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device1_name)
    device2 = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device2_name)
    role_peer = "peer"

    peer_intfs_dev1 = sorted(
        await client.filters(
            branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device1.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )
    peer_intfs_dev2 = sorted(
        await client.filters(
            branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device2.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )

    # Querying the object for now, need to pull from the store instead
    peer_ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": peer_intfs_dev1[0].id},
        address=f"{str(next(new_peer_network_hosts))}/31",
    )
    await peer_ip.save()
    log.info(f" - Replaced {device1_name}-{peer_intfs_dev1[0].name.value} IP to {peer_ip.address.value}")

    ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": peer_intfs_dev2[0].id},  # , "source": account_pop.id},
        address={"value": f"{str(next(new_peer_network_hosts))}/31"},  # , "source": account_pop.id},
    )
    await ip.save()
    log.info(f" - Replaced {device2_name}-{peer_intfs_dev2[0].name.value} IP to {ip.address.value}")


async def branch_scenario_remove_colt(client: InfrahubClient, log: logging.Logger, site_name: str) -> None:
    """
    Create a new Branch and Delete Colt Upstream Circuit
    """
    log.info("Create a new Branch and Delete Colt Upstream Circuit")
    new_branch_name = f"{site_name}-delete-upstream"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Delete upstream circuit with colt in {site_name}",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    # TODO need to update the role on the interface and need to delete the IP Address
    # for idx in range(1, 3):
    #     device_name = f"{site_name}-edge{idx}"
    #     device = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device_name)
    #     intf = await client.get(branch=new_branch_name, kind="InfraInterfaceL3", device__id=device.id, name__value="Ethernet5")

    # Delete circuits
    get_circuits_query = """
    query($site_name: String!) {
        InfraCircuitEndpoint(site__name__value: $site_name) {
            edges {
                node {
                    id
                    circuit {
                        node {
                            id
                            circuit_id {
                                value
                            }
                            provider {
                                node {
                                    name {
                                        value
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    circuits = await client.execute_graphql(
        branch_name=new_branch_name, query=get_circuits_query, variables={"site_name": site_name}
    )
    colt_circuits = [
        circuit
        for circuit in circuits["InfraCircuitEndpoint"]["edges"]
        if circuit["node"]["circuit"]["node"]["provider"]["node"]["name"]["value"] == "Colt Technology Services"
    ]

    for item in colt_circuits:
        circuit_id = item["node"]["circuit"]["node"]["circuit_id"]["value"]
        circuit_endpoint = await client.get(branch=new_branch_name, kind=InfraCircuitEndpoint, id=item["node"]["id"])
        await circuit_endpoint.delete()

        circuit = await client.get(branch=new_branch_name, kind=InfraCircuit, id=item["node"]["circuit"]["node"]["id"])
        await circuit.delete()
        log.info(f" - Deleted Colt Technology Services [{circuit_id}]")


async def branch_scenario_conflict_device(client: InfrahubClient, log: logging.Logger, site_name: str) -> None:
    """
    Create a new Branch and introduce some conflicts
    """
    log.info("Create a new Branch and introduce some conflicts")
    device1_name = f"{site_name}-edge1"
    f"{site_name}-edge2"

    new_branch_name = f"{site_name}-maintenance-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Put {device1_name} in maintenance mode",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    maintenance_status = "maintenance"
    provisioning_status = "provisioning"
    drained_status = "drained"

    # Update Device 1 Status both in the Branch and in Main
    device1_branch = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device1_name)

    device1_branch.status.value = maintenance_status
    await device1_branch.save()

    intf1_branch = await client.get(
        branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device1_branch.id], name__value="Ethernet1"
    )
    intf1_branch.enabled.value = False
    intf1_branch.status.value = drained_status
    await intf1_branch.save()

    device1_main = await client.get(kind=InfraDevice, name__value=device1_name)

    device1_main.status.value = provisioning_status
    await device1_main.save()

    intf1_main = await client.get(kind=InfraInterfaceL3, device__ids=[device1_branch.id], name__value="Ethernet1")
    intf1_main.enabled.value = False
    await intf1_main.save()


async def branch_scenario_conflict_platform(client: InfrahubClient, log: logging.Logger) -> None:
    """
    Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE
    """
    log.info("Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE")
    new_branch_name = "platform-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description="Add new platform",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    # Create a new Platform object with the same name, both in the branch and in main
    platform1_branch = await client.create(
        branch=new_branch_name, kind=InfraPlatform, name="Cisco IOS XR", netmiko_device_type="cisco_xr"
    )
    await platform1_branch.save()
    platform1_main = await client.create(kind=InfraPlatform, name="Cisco IOS XR", netmiko_device_type="cisco_xr")
    await platform1_main.save()

    # Delete an existing Platform object on both in the Branch and in Main
    platform2_branch = await client.get(branch=new_branch_name, kind=InfraPlatform, name__value="Cisco NXOS SSH")
    await platform2_branch.delete()
    platform2_main = await client.get(kind=InfraPlatform, name__value="Cisco NXOS SSH")
    await platform2_main.delete()

    # Delete an existing Platform object in the branch and update it in main
    platform3_branch = await client.get(branch=new_branch_name, kind=InfraPlatform, name__value="Juniper JunOS")
    await platform3_branch.delete()
    platform3_main = await client.get(kind=InfraPlatform, name__value="Juniper JunOS")
    platform3_main.nornir_platform.value = "juniper_junos"
    await platform3_main.save()


async def generate_continents_countries(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    continent_batch = await client.create_batch()
    country_batch = await client.create_batch()

    for continent, countries in CONTINENT_COUNTRIES.items():
        continent_obj = await client.create(branch=branch, kind=LocationContinent, name=continent)
        continent_batch.add(task=continent_obj.save, node=continent_obj)
        client.store.set(node=continent_obj)

        for country in countries:
            country_obj = await client.create(branch=branch, kind=LocationCountry, name=country, parent=continent_obj)
            country_batch.add(task=country_obj.save, node=country_obj)
            client.store.set(node=country_obj)

    async for node, _ in continent_batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.name.value}")

    async for node, _ in country_batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.name.value}")

    log.info("Created continents and countries")


async def prepare_permissions(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for p in GLOBAL_PERMISSIONS:
        obj = await client.get(
            branch=branch,
            kind=CoreGlobalPermission,
            hfid=[p.action, str(p.decision)],
        )
        client.store.set(key=p.action, node=obj)

    for name, p in OBJECT_PERMISSIONS.items():
        try:
            obj = await client.get(
                branch=branch, kind="CoreObjectPermission", hfid=[p.namespace, p.name, p.action, str(p.decision)]
            )
        except NodeNotFoundError:
            obj = await client.create(branch=branch, kind="CoreObjectPermission", data=p.model_dump())
            batch.add(task=obj.save, node=obj)
        client.store.set(key=name, node=obj)


async def prepare_account_roles(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for role in ACCOUNT_ROLES:
        obj = await client.create(
            branch=branch,
            kind="CoreAccountRole",
            data=role.model_dump(exclude={"global_permissions", "object_permissions"}),
        )
        batch.add(task=obj.save, node=obj)
        client.store.set(key=role.name, node=obj)


async def prepare_accounts(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for account in ACCOUNTS:
        obj = await client.create(branch=branch, kind=CoreAccount, data=account.model_dump(exclude={"groups"}))
        batch.add(task=obj.save, allow_upsert=True, node=obj)
        client.store.set(key=account.name, node=obj)

    for name, group in ACCOUNT_GROUPS.items():
        obj = await client.create(
            branch=branch, kind=CoreAccountGroup, data=group.model_dump(exclude={"roles", "members"})
        )
        batch.add(task=obj.save, allow_upsert=True, node=obj)
        client.store.set(key=name, node=obj)


async def map_permissions_to_roles(
    client: InfrahubClient,
    log: logging.Logger,  # noqa: ARG001
    branch: str,  # noqa: ARG001
    batch: InfrahubBatch,
) -> None:
    for role in ACCOUNT_ROLES:
        if not role.global_permissions and not role.object_permissions:
            continue

        obj = client.store.get(key=[role.name], kind=CoreAccountRole)
        await obj.permissions.fetch()

        permissions: list[CoreGlobalPermission | CoreObjectPermission] = []
        if role.global_permissions:
            if isinstance(role.global_permissions, str) and role.global_permissions == "__all__":
                permissions.extend(
                    [
                        client.store.get(
                            p.action,
                            kind=CoreGlobalPermission,
                        )
                        for p in GLOBAL_PERMISSIONS
                    ]
                )
            else:
                permissions.extend(
                    [
                        client.store.get(
                            p_name,
                            kind=CoreGlobalPermission,
                        )
                        for p_name in role.global_permissions
                    ]
                )
        if role.object_permissions:
            if isinstance(role.object_permissions, str) and role.object_permissions == "__all__":
                permissions.extend(
                    [
                        client.store.get(
                            p_name,
                            kind=CoreObjectPermission,
                        )
                        for p_name in GLOBAL_PERMISSIONS
                    ]
                )
            else:
                permissions.extend(
                    [
                        client.store.get(
                            p_name,
                            kind=CoreObjectPermission,
                        )
                        for p_name in role.object_permissions
                    ]
                )

        obj.permissions.extend(permissions)
        batch.add(task=obj.save, node=obj)


async def map_user_and_roles_to_groups(
    client: InfrahubClient,
    log: logging.Logger,  # noqa: ARG001
    branch: str,  # noqa: ARG001
    batch: InfrahubBatch,
) -> None:
    for group_name, group in ACCOUNT_GROUPS.items():
        updated = False
        obj = client.store.get(
            group_name,
            kind=CoreAccountGroup,
        )

        if group.roles:
            await obj.roles.fetch()
            obj.roles.extend(
                data=[
                    client.store.get(
                        role,
                        kind=CoreAccountRole,
                    )
                    for role in group.roles
                ]
            )
            updated = True
        if group.members:
            await obj.members.fetch()
            obj.members.extend(
                data=[
                    client.store.get(
                        member,
                        kind=CoreAccount,
                    )
                    for member in group.members
                ]
            )
            updated = True

        if updated:
            batch.add(task=obj.save, node=obj)


async def prepare_asns(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    account_chloe = client.store.get(
        "cobrian",
        kind=CoreAccount,
    )
    account_crm = client.store.get(
        "crm-sync",
        kind=CoreAccount,
    )
    organizations_dict = {org.name: org.type for org in ORGANIZATIONS}
    for asn in ASNS:
        organization_type = organizations_dict.get(asn.organization)
        asn_name = f"AS{asn.asn}"
        data_asn = {
            "name": {"value": asn.name, "source": account_crm.id, "owner": account_chloe.id},
            "asn": {"value": asn.asn, "source": account_crm.id, "owner": account_chloe.id},
        }
        if organization_type:
            data_asn["description"] = {
                "value": f"{asn_name} for {asn.organization}",
                "source": account_crm.id,
                "owner": account_chloe.id,
            }
            data_asn["organization"] = {
                "id": client.store.get(kind=f"Organization{organization_type.title()}", key=asn.organization).id,
                "source": account_crm.id,
            }
        else:
            data_asn["description"] = {"value": f"{asn_name}", "source": account_crm.id, "owner": account_chloe.id}
        obj = await client.create(branch=branch, kind="InfraAutonomousSystem", data=data_asn)
        batch.add(task=obj.save, node=obj)
        client.store.set(key=asn.organization, node=obj)


async def prepare_bgp_peer_groups(
    client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch
) -> None:
    account_pop = client.store.get(
        "pop-builder",
        kind=CoreAccount,
    )

    log.info("Creating BGP Peer Groups")
    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        local_as_id = None
        local_as = client.store.get(kind=InfraAutonomousSystem, key=peer_group.local_as, raise_when_missing=False)
        remote_as = (
            client.store.get(kind=InfraAutonomousSystem, key=peer_group.remote_as, raise_when_missing=False)
            if peer_group.remote_as
            else None
        )
        if remote_as:
            remote_as_id = remote_as.id
        if local_as:
            local_as_id = local_as.id

        obj = await client.create(
            branch=branch,
            kind=InfraBGPPeerGroup,
            name={"value": peer_group.name, "source": account_pop.id},
            import_policies={"value": peer_group.import_policies, "source": account_pop.id},
            export_policies={"value": peer_group.export_policies, "source": account_pop.id},
            local_as={"id": local_as_id},
            remote_as={"id": remote_as_id},
        )
        batch.add(task=obj.save, node=obj)
        client.store.set(node=obj)


async def prepare_groups(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for group in GROUPS:
        obj = await client.create(branch=branch, kind=CoreStandardGroup, data=group.model_dump())

        batch.add(task=obj.save, node=obj)
        client.store.set(key=group.name, node=obj)


async def prepare_interface_profiles(
    client: InfrahubClient,
    log: logging.Logger,  # noqa: ARG001
    branch: str,
    batch: InfrahubBatch,
) -> None:
    for intf_profile in INTERFACE_PROFILES:
        data_profile = {
            "profile_name": {"value": intf_profile.name},
            "mtu": {"value": intf_profile.mtu},
        }
        profile = await client.create(branch=branch, kind=intf_profile.profile_kind, data=data_profile)
        batch.add(task=profile.save, node=profile)
        client.store.set(key=intf_profile.name, node=profile)


async def prepare_organizations(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for org in ORGANIZATIONS:
        data_org = {
            "name": {"value": org.name, "is_protected": True},
        }
        obj = await client.create(branch=branch, kind=org.kind, data=data_org)
        batch.add(task=obj.save, node=obj)
        client.store.set(key=org.name, node=obj)


async def prepare_platforms(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:  # noqa: ARG001
    for platform in PLATFORMS:
        obj = await client.create(
            branch=branch,
            kind=InfraPlatform,
            data=platform.model_dump(),
        )
        batch.add(task=obj.save, node=obj)
        client.store.set(key=platform.name, node=obj)


async def prepare_tags(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    account_pop = client.store.get(
        "pop-builder",
        kind=CoreAccount,
    )

    log.info("Creating Tags")
    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        client.store.set(key=tag, node=obj)


async def prepare_patch_template(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    log.info("Creating Patch Panel Template")
    batch = await client.create_batch()

    # Create Patch Panel Template
    for template in TEMPLATES:
        patch_template = await client.create(branch=branch, kind="TemplateInfraPatchPanel", data=template.model_dump())
        await patch_template.save(allow_upsert=True)

        # and corresponding interfaces
        for interface in template.interfaces:
            interface.patch_panel = {"id": patch_template.id}
            obj = await client.create(
                branch=branch,
                kind="TemplateInfraFrontPatchPanelInterface",
                data=interface.model_dump(),
            )
            batch.add(task=obj.save, node=obj)

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# You can also provide inputs to the script in order to generate more or less data
#
#   infrahubctl run models/infrastructure_edge.py profile="large"
#   infrahubctl run models/infrastructure_edge.py num_sites=10 num_device_per_site=14
#   infrahubctl run models/infrastructure_edge.py has_bgp_mesh=False has_branch=False
#
# ---------------------------------------------------------------
async def run(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    profile: str | None = None,
    num_sites: int | None = None,
    num_device_per_site: int | None = None,
    has_bgp_mesh: str | None = None,
    has_branch: str | None = None,
) -> None:
    # Create timer to keep track of time elapsed
    start: float = time.time()

    branch = branch or "main"

    # ------------------------------------------
    # Config
    # ------------------------------------------
    # Create an instance of the global configuration
    config = GlobalConfig()

    # Translate str to bool
    bool_has_bgp_mesh: bool | None = None
    if has_bgp_mesh is not None:
        bool_has_bgp_mesh = translate_str_to_bool("has_bgp_mesh", has_bgp_mesh)

    bool_has_branch: bool | None = None
    if has_branch is not None:
        bool_has_branch = translate_str_to_bool("has_branch", has_branch)

    # Load args into the config
    try:
        config.load_config(profile, num_sites, num_device_per_site, bool_has_bgp_mesh, bool_has_branch)
    except ConfigError as ex:
        log.fatal(ex)
        return

    log.info(f"Loading data with {config}")

    # ------------------------------------------
    # Create Continents, Countries
    # ------------------------------------------
    num_sites = int(config.num_sites)
    log.info("Creating Infrastructure Data")

    await generate_continents_countries(client=client, log=log, branch=branch)

    # ------------------------------------------
    # Create User Accounts, Groups, Organizations & Platforms
    # ------------------------------------------
    log.info("Creating User Accounts, Groups, Roles, Permissions & Organizations & Platforms")

    batch = await client.create_batch()
    await prepare_permissions(client=client, log=log, branch=branch, batch=batch)
    await prepare_account_roles(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        if hasattr(node, "name"):
            log.info(f"- Created {node.get_kind()} - {node.name.value}")
        else:
            log.info(f"- Created {node.get_kind()} - {node}")

    batch = await client.create_batch()
    await prepare_accounts(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.name.value}")

    batch = await client.create_batch()
    await map_permissions_to_roles(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        log.info(f"- Updated {node.get_kind()} - {node.name.value} with permissions")

    batch = await client.create_batch()
    await map_user_and_roles_to_groups(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        log.info(f"- Updated {node.get_kind()} - {node.name.value} with roles and members")

    await prepare_groups(client=client, log=log, branch=branch, batch=batch)
    await prepare_platforms(client=client, log=log, branch=branch, batch=batch)
    await prepare_organizations(client=client, log=log, branch=branch, batch=batch)
    await prepare_interface_profiles(client=client, log=log, branch=branch, batch=batch)

    async for node, _ in batch.execute():
        if node._schema.namespace == "Profile":
            log.info(f"- Created {node.get_kind()} - {node.profile_name.value}")
        else:
            log.info(f"- Created {node.get_kind()} - {node.name.value}")

    account_pop = client.store.get(
        "pop-builder",
        kind=CoreAccount,
    )

    batch = await client.create_batch()
    await prepare_asns(client=client, log=log, branch=branch, batch=batch)
    await prepare_tags(client=client, log=log, branch=branch, batch=batch)

    async for node, _ in batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.name.value}")

    batch = await client.create_batch()
    await prepare_bgp_peer_groups(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        log.info(f"- Created {node.get_kind()} - {node.name.value}")

    # ------------------------------------------
    # Create IP prefixes
    # ------------------------------------------
    default_ip_namespace = await client.get(kind=IpamNamespace, name__value="default")

    log.info("Creating IP Prefixes")

    log.info("Creating IP Core Supernet and Pool")
    supernet_prefix = await client.create(
        branch=branch, kind=IpamIPPrefix, prefix=str(NETWORKS_SUPERNET), member_type="prefix"
    )
    await supernet_prefix.save()
    supernet_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Internal networks pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=16,
        ip_namespace=default_ip_namespace,
        resources=[supernet_prefix],
        branch=branch,
    )
    # Using upsert for branch agnostic nodes in order to execute the script in different branches during development
    await supernet_pool.save(allow_upsert=True)

    log.info("Creating IP Loopback Prefix and Pool")
    loopback_prefix = await client.allocate_next_ip_prefix(
        resource_pool=supernet_pool, member_type="address", branch=branch
    )
    loopback_pool = await client.create(
        kind=CoreIPAddressPool,
        name="Loopbacks pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=32,
        ip_namespace=default_ip_namespace,
        resources=[loopback_prefix],
        branch=branch,
    )
    await loopback_pool.save(allow_upsert=True)

    log.info("Creating IP Interconnection Prefix and Pool")
    interconnection_prefix = await client.allocate_next_ip_prefix(
        kind=IpamIPPrefix, resource_pool=supernet_pool, branch=branch
    )
    interconnection_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Interconnections pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=31,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[interconnection_prefix],
        branch=branch,
    )
    await interconnection_pool.save(allow_upsert=True)
    client.store.set(node=interconnection_pool)

    # Allocate an empty prefix
    await client.allocate_next_ip_prefix(resource_pool=supernet_pool, branch=branch)

    log.info("Creating IP Management Prefix and Pool")
    management_prefix = await client.create(
        branch=branch, kind=IpamIPPrefix, prefix=str(MANAGEMENT_NETWORKS), member_type="address"
    )
    await management_prefix.save(allow_upsert=True)
    management_pool = await client.create(
        kind=CoreIPAddressPool,
        name="Management addresses pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=16,
        ip_namespace=default_ip_namespace,
        resources=[management_prefix],
        branch=branch,
    )
    await management_pool.save(allow_upsert=True)

    log.info("Creating IP External Supernet and Pool")
    external_supernet = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_POOL_EXTERNAL_SUPERNET), member_type="prefix"
    )
    await external_supernet.save()
    external_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="External prefixes pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=29,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[external_supernet],
        branch=branch,
    )
    await external_pool.save(allow_upsert=True)

    log.info("Creating IPv6 Core Supernet and Pool")
    ipv6_supernet_prefix = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_SUPERNET_IPV6), member_type="prefix"
    )
    await ipv6_supernet_prefix.save()
    ipv6_supernet_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Internal networks pool (IPv6)",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=110,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[ipv6_supernet_prefix],
        branch=branch,
    )
    await ipv6_supernet_pool.save(allow_upsert=True)

    # ------------------------------------------
    # Create Pool IPv6 prefixes
    # ------------------------------------------
    log.info("Creating pool IPv6 Prefixes and IPs")
    ipv6_internal_networks: list[IpamIPPrefix] = [
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
    ]

    log.info("IP Prefixes Creation Completed")

    # ------------------------------------------
    # Create IPv6 IP from IPv6 Prefix pool
    # ------------------------------------------
    ipv6_addresses = []
    for index, network in enumerate(ipv6_internal_networks[:4]):
        multiplier = index + 1
        host_list = list(network.prefix.value.hosts())
        number_of_hosts = min(multiplier * 17, len(host_list))
        ipv6_addresses.extend(host_list[:number_of_hosts])

    batch = await client.create_batch()
    for ipv6_addr in ipv6_addresses:
        obj = await client.create(
            branch=branch, kind=IpamIPAddress, address={"value": ipv6_addr, "source": account_pop.id}
        )
        batch.add(task=obj.save, node=obj)

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")

    log.info("IPv6 Address Creation Completed")

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site and associated objects (Device, Circuit, BGP Sessions)")
    sites = site_generator(nbr_site=num_sites)

    # Compute the design to follow for each site
    site_design: SiteDesign = SiteDesign(config.num_device_per_site)
    log.info(f"following {site_design}")

    for site in sites:
        response = await generate_site(
            client=client,
            log=log,
            branch=branch,
            site=site,
            interconnection_pool=interconnection_pool,
            loopback_pool=loopback_pool,
            management_pool=management_pool,
            external_pool=external_pool,
            site_design=site_design,
        )
        log.info(f"{response} - Creation Completed")

    # await apply_interface_profiles(
    #     client=client,
    #     branch=branch,
    #     log=log,
    # )
    await apply_interface_profiles_and_groups(
        client=client,
        branch=branch,
        log=log,
    )
    await apply_devices_groups(
        client=client,
        branch=branch,
        log=log,
    )

    if config.has_bgp_mesh:
        await create_bgp_mesh(client=client, branch=branch, log=log, sites=sites)

    await create_backbone_connectivity(client=client, branch=branch, log=log, num_sites=num_sites)

    await prepare_patch_template(client=client, log=log, branch=branch)

    # --------------------------------------------------
    # Create some changes in additional branches
    #  Scenario 1 - Add a Peering
    #  Scenario 2 - Change the IP Address between 2 edges
    #  Scenario 3 - Delete a Circuit + Peering
    #  Scenario 4 - Create some Relationship One and Attribute conflicts on a device
    #  Scenario 5 - Create some Node ADD and DELETE conflicts on some platform objects
    # --------------------------------------------------
    if branch == "main" and config.has_branch:
        # await branch_scenario_add_upstream(site_name=sites[1].name, client=client, log=log,
        # await branch_scenario_replace_ip_addresses(
        #     site_name=sites[2].name, client=client, log=log
        # )
        # await branch_scenario_remove_colt(site_name=sites[0].name, client=client, log=log)
        # await branch_scenario_conflict_device(site_name=sites[3].name, client=client, log=log)
        # await branch_scenario_conflict_platform(client=client, log=log)
        batch = await client.create_batch()

        batch.add(
            task=branch_scenario_add_upstream,
            site_name=sites[1].name,
            client=client,
            log=log,
            external_pool=external_pool,  # Could be load from store
        )

        batch.add(
            task=branch_scenario_replace_ip_addresses,
            site_name=sites[2].name,
            client=client,
            log=log,
            interconnection_pool=interconnection_pool,  # Could be load from store
        )
        batch.add(task=branch_scenario_remove_colt, site_name=sites[0].name, client=client, log=log)
        batch.add(task=branch_scenario_conflict_device, site_name=sites[3].name, client=client, log=log)
        batch.add(task=branch_scenario_conflict_platform, client=client, log=log)

        async for node, _ in batch.execute():
            log.debug(f"Branch scenario {node} completed")

    # Stop the timer and display elapsed time
    log.info(f"Data loaded in {round(time.time() - start)}s")
