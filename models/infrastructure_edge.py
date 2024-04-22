import logging
import random
import uuid
from itertools import islice
from collections import defaultdict
from ipaddress import IPv4Network, IPv6Network
from typing import Dict, List

from infrahub_sdk import UUIDT, InfrahubClient, InfrahubNode, NodeStore
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.graphql import Mutation

# flake8: noqa
# pylint: skip-file

CONTINENT_COUNTRIES = {
    "North America": ["United States of America", "Canada"],
    "South America": ["Mexico", "Brazil"],
    "Africa": ["Morocco", "Senegal"],
    "Europe": ["France", "Spain", "Italy"],
    "Asia": ["Japan", "China"],
    "Oceania": ["Australia", "New Zealand"],
}

SITES = [
    {"name": "atl", "country": "United States of America", "city": "Atlanta", "contact": "Bailey Li"},
    {"name": "ord", "country": "United States of America", "city": "Chicago", "contact": "Kayden Kennedy"},
    {"name": "jfk", "country": "United States of America", "city": "New York", "contact": "Micaela Marsh"},
    {"name": "den", "country": "United States of America", "city": "Denver", "contact": "Francesca Wilcox"},
    {"name": "dfw", "country": "United States of America", "city": "Dallas", "contact": "Carmelo Moran"},
    {"name": "iad", "country": "United States of America", "city": "Washington D.C.", "contact": "Avery Jimenez"},
    {"name": "sea", "country": "United States of America", "city": "Seattle", "contact": "Charlotte Little"},
    {"name": "sfo", "country": "United States of America", "city": "San Francisco", "contact": "Taliyah Sampson"},
    {"name": "iah", "country": "United States of America", "city": "Houston", "contact": "Fernanda Solomon"},
    {"name": "mco", "country": "United States of America", "city": "Orlando", "contact": "Arthur Rose"},
]

PLATFORMS = (
    ("Cisco IOS", "ios", "ios", "cisco_ios", "ios"),
    ("Cisco NXOS SSH", "nxos_ssh", "nxos_ssh", "cisco_nxos", "nxos"),
    ("Juniper JunOS", "junos", "junos", "juniper_junos", "junos"),
    ("Arista EOS", "eos", "eos", "arista_eos", "eos"),
)

DEVICES = (
    ("edge1", "active", "7280R3", "profile1", "edge", ["red", "green"], "Arista EOS"),
    ("edge2", "active", "ASR1002-HX", "profile1", "edge", ["red", "blue", "green"], "Cisco IOS"),
    ("core1", "drained", "MX204", "profile1", "core", ["blue"], "Juniper JunOS"),
    ("core2", "provisioning", "MX204", "profile1", "core", ["red"], "Juniper JunOS"),
)


NETWORKS_SUPERNET = IPv4Network("10.0.0.0/8")
NETWORKS_SUPERNET_IPV6 = IPv6Network("2001:DB8::/112")
NETWORKS_POOL_INTERNAL = list(NETWORKS_SUPERNET.subnets(new_prefix=16))
NETWORKS_POOL_INTERNAL_IPV6 = list(islice(NETWORKS_SUPERNET_IPV6.subnets(new_prefix=120), 6))
LOOPBACK_POOL = NETWORKS_POOL_INTERNAL[0].hosts()
P2P_NETWORK_POOL = NETWORKS_POOL_INTERNAL[1].subnets(new_prefix=31)
NETWORKS_POOL_EXTERNAL_SUPERNET = IPv4Network("203.0.113.0/24")
NETWORKS_POOL_EXTERNAL = NETWORKS_POOL_EXTERNAL_SUPERNET.subnets(new_prefix=29)
MANAGEMENT_NETWORKS = IPv4Network("172.20.20.0/27")
MANAGEMENT_IPS = MANAGEMENT_NETWORKS.hosts()

ACTIVE_STATUS = "active"
BACKBONE_ROLE = "backbone"


def site_generator(nbr_site=2) -> List[Dict[str, str]]:
    """Generate a list of site names by iterating over the list of SITES defined above and by increasing the id.

    site_names_generator(nbr_site=5)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1"]

    site_names_generator(nbr_site=12)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1", "iad1", "bkk1", "sfo1", "iah1", "mco1", "atl2", "ord2"]
    """

    sites: List[Dict[str, str]] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        sites.extend([{**site, **{"name": f"{site['name']}{idx}"}} for site in SITES[:nbr_this_loop]])

    return sites


P2P_NETWORKS_POOL = {
    ("atl1", "edge1", "ord1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
    ("atl1", "edge1", "jfk1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
    ("jfk1", "edge1", "ord1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
    ("atl1", "edge2", "ord1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
    ("atl1", "edge2", "jfk1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
    ("jfk1", "edge2", "ord1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
}

BACKBONE_CIRCUIT_IDS = [
    "DUFF-1543451",
    "DUFF-6535773",
    "DUFF-5826854",
    "DUFF-8263953",
    "DUFF-7324064",
    "DUFF-4867430",
    "DUFF-4654456",
]

INTERFACE_MGMT_NAME = {
    "7280R3": "Management0",
    "ASR1002-HX": "Management0",
    "MX204": "MGMT",
}

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
    "MX204": ["et-0/0/0", "et-0/0/1", "et-0/0/2"],
}
INTERFACE_L2_NAMES = {
    "7280R3": ["Ethernet11", "Ethernet12"],
    "ASR1002-HX": ["Ethernet11", "Ethernet12"],
    "MX204": ["et-0/0/3"],
}

INTERFACE_ROLES_MAPPING = {
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
}

TAGS = ["blue", "green", "red"]

ORGANIZATIONS = (
    # name, type
    ("Arelion", "provider"),
    ("Colt Technology Services", "provider"),
    ("Verizon Business", "provider"),
    ("GTT Communications", "provider"),
    ("Hurricane Electric", "provider"),
    ("Lumen", "provider"),
    ("Zayo", "provider"),
    ("Equinix", "provider"),
    ("Interxion", "provider"),
    ("PCCW Global", "provider"),
    ("Orange S.A", "provider"),
    ("Tata Communications", "provider"),
    ("Sprint", "provider"),
    ("NTT America", "provider"),
    ("Cogent Communications", "provider"),
    ("Comcast Cable Communication", "provider"),
    ("Telecom Italia Sparkle", "provider"),
    ("AT&T Services", "provider"),
    ("Duff", "tenant"),
    ("Juniper", "manufacturer"),
    ("Cisco", "manufacturer"),
    ("Arista", "manufacturer"),
)

ASNS = (
    # asn, organization
    (1299, "Arelion"),
    (64496, "Duff"),
    (8220, "Colt Technology Services"),
    (701, "Verizon Business"),
    (3257, "GTT Communications"),
    (6939, "Hurricane Electric"),
    (3356, "Lumen"),
    (6461, "Zayo"),
    (24115, "Equinix"),
    (20710, "Interxion"),
    (3491, "PCCW Global"),
    (5511, "Orange S.A"),
    (6453, "Tata Communications"),
    (1239, "Sprint"),
    (2914, "NTT America"),
    (174, "Cogent Communications"),
    (7922, "Comcast Cable Communication"),
    (6762, "Telecom Italia Sparkle"),
    (7018, "AT&T Services"),
)

INTERFACE_OBJS: Dict[str, List[InfrahubNode]] = defaultdict(list)

ACCOUNTS = (
    ("pop-builder", "Script", "Password123", "read-write"),
    ("CRM Synchronization", "Script", "Password123", "read-write"),
    ("Jack Bauer", "User", "Password123", "read-only"),
    ("Chloe O'Brian", "User", "Password123", "read-write"),
    ("David Palmer", "User", "Password123", "read-write"),
    ("Operation Team", "User", "Password123", "read-only"),
    ("Engineering Team", "User", "Password123", "read-write"),
    ("Architecture Team", "User", "Password123", "read-only"),
)


GROUPS = (
    ("edge_router", "Edge Router"),
    ("core_router", "Core Router"),
    ("cisco_devices", "Cisco Devices"),
    ("arista_devices", "Arista Devices"),
    ("upstream_interfaces", "Upstream Interfaces"),
    ("backbone_interfaces", "Backbone Interfaces"),
)

BGP_PEER_GROUPS = (
    ("POP_INTERNAL", "IMPORT_INTRA_POP", "EXPORT_INTRA_POP", "Duff", "Duff"),
    ("POP_GLOBAL", "IMPORT_POP_GLOBAL", "EXPORT_POP_GLOBLA", "Duff", None),
    ("UPSTREAM_DEFAULT", "IMPORT_UPSTREAM", "EXPORT_PUBLIC_PREFIX", "Duff", None),
    ("UPSTREAM_ARELION", "IMPORT_UPSTREAM", "EXPORT_PUBLIC_PREFIX", "Duff", "Arelion"),
    ("IX_DEFAULT", "IMPORT_IX", "EXPORT_PUBLIC_PREFIX", "Duff", None),
)

INTERFACE_PROFILES = (
    # profile_name, mtu
    ("upstream_profile", 1515, "InfraInterfaceL3"),
    ("backbone_profile", 9216, "InfraInterfaceL3"),
)

VLANS = (
    ("200", "server"),
    ("400", "management"),
)

store = NodeStore()


async def generate_site(client: InfrahubClient, log: logging.Logger, branch: str, site: Dict[str, str]):
    group_eng = store.get("Engineering Team")
    group_ops = store.get("Operation Team")
    account_pop = store.get("pop-builder")
    account_crm = store.get("CRM Synchronization")
    internal_as = store.get(kind="InfraAutonomousSystem", key="Duff")

    group_edge_router = store.get(kind="CoreStandardGroup", key="edge_router")
    await group_edge_router.members.fetch()
    group_core_router = store.get(kind="CoreStandardGroup", key="core_router")
    await group_core_router.members.fetch()
    group_cisco_devices = store.get(kind="CoreStandardGroup", key="cisco_devices")
    await group_cisco_devices.members.fetch()
    group_arista_devices = store.get(kind="CoreStandardGroup", key="arista_devices")
    await group_arista_devices.members.fetch()
    group_upstream_interfaces = store.get(kind="CoreStandardGroup", key="upstream_interfaces")
    await group_upstream_interfaces.members.fetch()
    group_backbone_interfaces = store.get(kind="CoreStandardGroup", key="backbone_interfaces")
    await group_backbone_interfaces.members.fetch()

    country = store.get(kind="LocationCountry", key=site["country"])
    # --------------------------------------------------
    # Create the Site
    # --------------------------------------------------
    site = await client.create(
        branch=branch,
        kind="LocationSite",
        name={"value": site["name"], "is_protected": True, "source": account_crm.id},
        contact={"value": site["contact"], "is_protected": True, "source": account_crm.id},
        city={"value": site["city"], "is_protected": True, "source": account_crm.id},
        parent=country,
    )
    await site.save()
    log.info(f"- Created {site._schema.kind} - {site.name.value}")

    site_name = site.name.value

    peer_networks = [next(P2P_NETWORK_POOL), next(P2P_NETWORK_POOL)]
    peer_network_hosts = {0: peer_networks[0].hosts(), 1: peer_networks[1].hosts()}

    # --------------------------------------------------
    # Create the site specific VLAN
    # --------------------------------------------------
    for vlan in VLANS:
        vlan_role = vlan[1]
        vlan_name = f"{site_name}_{vlan[1]}"
        obj = await client.create(
            branch=branch,
            kind="InfraVLAN",
            site={"id": site.id, "source": account_pop.id, "is_protected": True},
            name={"value": f"{site_name}_{vlan[1]}", "is_protected": True, "source": account_pop.id},
            vlan_id={"value": int(vlan[0]), "is_protected": True, "owner": group_eng.id, "source": account_pop.id},
            status={"value": ACTIVE_STATUS, "owner": group_ops.id},
            role={"value": vlan_role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
        )
        await obj.save()
        store.set(key=vlan_name, node=obj)

    # --------------------------------------------------
    # Create the site specific IP prefixes
    # --------------------------------------------------
    for net in peer_networks:
        prefix = await client.create(branch=branch, kind="IpamIPPrefix", prefix=str(net))
        await prefix.save()

    for idx, device in enumerate(DEVICES):
        device_name = f"{site_name}-{device[0]}"
        device_status = device[1]
        device_role = device[4]
        device_type = device[2]
        platform_id = store.get(kind="InfraPlatform", key=device[6]).id

        obj = await client.create(
            branch=branch,
            kind="InfraDevice",
            site={"id": site.id, "source": account_pop.id, "is_protected": True},
            name={"value": device_name, "source": account_pop.id, "is_protected": True},
            status={"value": device_status, "owner": group_ops.id},
            type={"value": device[2], "source": account_pop.id},
            role={"value": device_role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            asn={"id": internal_as.id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            tags=[store.get(kind="BuiltinTag", key=tag_name).id for tag_name in device[5]],
            platform={"id": platform_id, "source": account_pop.id, "is_protected": True},
        )
        await obj.save()
        store.set(key=device_name, node=obj)
        log.info(f"- Created {obj._schema.kind} - {obj.name.value}")

        # Add device to groups
        if "edge" in device_role:
            group_edge_router.members.add(obj)
        elif "core" in device_role:
            group_core_router.members.add(obj)

        if "Arista" in device[6]:
            group_arista_devices.members.add(obj)
        elif "Cisco" in device[6]:
            group_cisco_devices.members.add(obj)

        # Loopback Interface
        intf = await client.create(
            branch=branch,
            kind="InfraInterfaceL3",
            device={"id": obj.id, "is_protected": True},
            name={"value": "Loopback0", "source": account_pop.id, "is_protected": True},
            enabled=True,
            status=ACTIVE_STATUS,
            role="loopback",
            speed=1000,
        )
        await intf.save()

        ip = await client.create(
            branch=branch,
            kind="IpamIPAddress",
            interface={"id": intf.id, "source": account_pop.id},
            address={"value": f"{str(next(LOOPBACK_POOL))}/32", "source": account_pop.id},
        )
        await ip.save()
        store.set(key=f"{device_name}-loopback", node=ip)

        # Management Interface
        intf = await client.create(
            branch=branch,
            kind="InfraInterfaceL3",
            device={"id": obj.id, "is_protected": True},
            name={"value": INTERFACE_MGMT_NAME[device_type], "source": account_pop.id},
            enabled={"value": True, "owner": group_eng.id},
            status={"value": ACTIVE_STATUS, "owner": group_eng.id},
            role={
                "value": "management",
                "source": account_pop.id,
                "is_protected": True,
            },
            speed=1000,
        )
        await intf.save()
        ip = await client.create(
            branch=branch, kind="IpamIPAddress", interface=intf.id, address=f"{str(next(MANAGEMENT_IPS))}/24"
        )
        await ip.save()

        # set the IP address of the device to the management interface IP address
        obj.primary_address = ip
        await obj.save()

        # L3 Interfaces
        for intf_idx, intf_name in enumerate(INTERFACE_L3_NAMES[device_type]):
            intf_role = INTERFACE_ROLES_MAPPING[device[4]][intf_idx]

            intf = await client.create(
                branch=branch,
                kind="InfraInterfaceL3",
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
            )
            await intf.save()

            store.set(key=f"{device_name}-l3-{intf_idx}", node=intf)
            if intf_role == "backbone":
                INTERFACE_OBJS[device_name].append(intf)
                group_backbone_interfaces.members.add(intf)

            subnet = None
            address = None
            if intf_role == "peer":
                address = f"{str(next(peer_network_hosts[intf_idx]))}/31"

            if intf_role == "upstream":
                group_upstream_interfaces.members.add(intf)

            if intf_role in ["upstream", "peering"] and "edge" in device_role:
                subnet = next(NETWORKS_POOL_EXTERNAL)
                subnet_hosts = subnet.hosts()
                address = f"{str(next(subnet_hosts))}/29"
                peer_address = f"{str(next(subnet_hosts))}/29"

            if not subnet:
                continue

            ip_prefix = await client.create(branch=branch, kind="IpamIPPrefix", prefix=str(subnet))
            await ip_prefix.save()

            if address:
                ip = await client.create(
                    branch=branch,
                    kind="IpamIPAddress",
                    interface={"id": intf.id, "source": account_pop.id},
                    address={"value": address, "source": account_pop.id},
                )
                await ip.save()

            # Create Circuit and BGP session for upstream and peering
            if intf_role in ["upstream", "peering"]:
                circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-{intf_role}-{address}"))))[24:]
                circuit_id = f"DUFF-{circuit_id_unique}"
                upstream_providers = ["Arelion", "Colt Technology Services"]

                if intf_role == "upstream":
                    provider_name = upstream_providers[intf_idx % 2]
                elif intf_role == "peering":
                    provider_name = "Equinix"

                provider = store.get(kind="OrganizationProvider", key=provider_name)

                circuit = await client.create(
                    branch=branch,
                    kind="InfraCircuit",
                    circuit_id=circuit_id,
                    vendor_id=f"{provider_name.upper()}-{UUIDT().short()}",
                    provider=provider.id,
                    status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                    role={
                        "value": intf_role,
                        "source": account_pop.id,
                        "owner": group_eng.id,
                    },
                )
                await circuit.save()
                log.info(f" - Created {circuit._schema.kind} - {provider_name} [{circuit.vendor_id.value}]")

                endpoint1 = await client.create(
                    branch=branch,
                    kind="InfraCircuitEndpoint",
                    site=site,
                    circuit=circuit.id,
                    connected_endpoint=intf.id,
                )
                await endpoint1.save()

                intf.description.value = f"Connected to {provider_name} via {circuit_id}"

                if intf_role == "upstream":
                    peer_group_name = (
                        "UPSTREAM_ARELION" if "arelion" in provider.name.value.lower() else "UPSTREAM_DEFAULT"
                    )

                    peer_ip = await client.create(
                        branch=branch,
                        kind="IpamIPAddress",
                        address=peer_address,
                    )
                    await peer_ip.save()

                    peer_as = store.get(kind="InfraAutonomousSystem", key=provider_name)
                    bgp_session = await client.create(
                        branch=branch,
                        kind="InfraBGPSession",
                        type="EXTERNAL",
                        local_as=internal_as.id,
                        local_ip=ip.id,
                        remote_as=peer_as.id,
                        remote_ip=peer_ip.id,
                        peer_group=store.get(key=peer_group_name).id,
                        device=store.get(key=device_name).id,
                        status=ACTIVE_STATUS,
                        role=intf_role,
                    )
                    await bgp_session.save()

                    log.debug(
                        f" - Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                    )

        # L2 Interfaces
        for intf_idx, intf_name in enumerate(INTERFACE_L2_NAMES[device_type]):
            intf_role = "server"

            intf = await client.create(
                branch=branch,
                kind="InfraInterfaceL2",
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
                l2_mode="Access",
                untagged_vlan={"id": store.get(kind="InfraVLAN", key=f"{site_name}_server").id},
            )
            await intf.save()

    # --------------------------------------------------
    # Connect both devices within the Site together with 2 interfaces
    # --------------------------------------------------
    for idx in range(0, 2):
        intf1 = store.get(kind="InfraInterfaceL3", key=f"{site_name}-edge1-l3-{idx}")
        intf2 = store.get(kind="InfraInterfaceL3", key=f"{site_name}-edge2-l3-{idx}")

        intf1.description.value = f"Connected to {site_name}-edge2 {intf2.name.value}"
        intf1.connected_endpoint = intf2
        await intf1.save()

        intf2.description.value = f"Connected to {site_name}-edge1 {intf1.name.value}"
        await intf2.save()

        log.info(f" - Connected '{site_name}-edge1::{intf1.name.value}' <> '{site_name}-edge2::{intf2.name.value}'")

    # --------------------------------------------------
    # Update all the group we may have touch during the site creation
    # --------------------------------------------------
    await group_upstream_interfaces.save()
    await group_backbone_interfaces.save()
    await group_edge_router.save()
    await group_core_router.save()
    await group_arista_devices.save()
    await group_cisco_devices.save()

    # --------------------------------------------------
    # Create iBGP Sessions within the Site
    # --------------------------------------------------
    for idx in range(0, 2):
        if idx == 0:
            device1 = f"{site_name}-{DEVICES[0][0]}"
            device2 = f"{site_name}-{DEVICES[1][0]}"
        elif idx == 1:
            device1 = f"{site_name}-{DEVICES[1][0]}"
            device2 = f"{site_name}-{DEVICES[0][0]}"

        peer_group_name = "POP_INTERNAL"

        loopback1 = store.get(key=f"{device1}-loopback")
        loopback2 = store.get(key=f"{device2}-loopback")

        obj = await client.create(
            branch=branch,
            kind="InfraBGPSession",
            type="INTERNAL",
            local_as=internal_as.id,
            local_ip=loopback1.id,
            remote_as=internal_as.id,
            remote_ip=loopback2.id,
            peer_group=store.get(key=peer_group_name).id,
            device=store.get(kind="InfraDevice", key=device1).id,
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        await obj.save()

        log.info(
            f" - Created BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
        )

    return site_name


async def branch_scenario_add_upstream(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site.
    """
    log.info("Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site")
    device_name = f"{site_name}-edge1"

    new_branch_name = f"{site_name}-add-upstream"
    new_branch = await client.branch.create(
        branch_name=new_branch_name, sync_with_git=False, description=f"Add a new Upstream link in {site_name}"
    )
    log.info(f"- Creating branch: {new_branch_name!r}")
    # Querying the object for now, need to pull from the store instead
    site = await client.get(branch=new_branch_name, kind="LocationSite", name__value=site_name)
    device = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device_name)
    gtt_organization = await client.get(
        branch=new_branch_name, kind="OrganizationProvider", name__value="GTT Communications"
    )

    role_spare = "spare"

    intfs = await client.filters(
        branch=new_branch_name, kind="InfraInterfaceL3", device__ids=[device.id], role__value=role_spare
    )
    intf = intfs[0]
    log.info(f" - Adding new Upstream on '{device_name}::{intf.name.value}'")

    # Allocate a new subnet and calculate new IP Addresses
    subnet = next(NETWORKS_POOL_EXTERNAL).hosts()
    address = f"{str(next(subnet))}/29"
    peer_address = f"{str(next(subnet))}/29"

    peer_ip = await client.create(
        branch=new_branch_name,
        kind="IpamIPAddress",
        address=peer_address,
    )
    await peer_ip.save()

    ip = await client.create(
        branch=new_branch_name,
        kind="IpamIPAddress",
        interface={"id": intf.id},
        address={"value": address},
    )
    await ip.save()

    circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-upstream-{address}"))))[24:]
    circuit_id = f"DUFF-{circuit_id_unique}"

    circuit = await client.create(
        branch=new_branch_name,
        kind="InfraCircuit",
        circuit_id=circuit_id,
        vendor_id=f"{gtt_organization.name.value.upper()}-{UUIDT().short()}",
        provider=gtt_organization.id,
        status=ACTIVE_STATUS,
        role="upstream",
    )
    await circuit.save()
    log.info(f"  - Created {circuit._schema.kind} - {gtt_organization.name.value} [{circuit.vendor_id.value}]")

    endpoint1 = await client.create(
        branch=new_branch_name,
        kind="InfraCircuitEndpoint",
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

    #     peer_as = store.get(kind="InfraAutonomousSystem", key=gtt_organization.name.value)
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


async def branch_scenario_replace_ip_addresses(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site
    """
    device1_name = f"{site_name}-edge1"
    device2_name = f"{site_name}-edge2"

    new_branch_name = f"{site_name}-update-edge-ips"
    new_branch = await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Change the IP addresses between edge1 and edge2 in {site_name}",
    )
    log.info("Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site")
    log.info(f"- Creating branch: {new_branch_name!r}")

    new_peer_network = next(P2P_NETWORK_POOL).hosts()

    device1 = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device1_name)
    device2 = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device2_name)
    role_peer = "peer"

    peer_intfs_dev1 = sorted(
        await client.filters(
            branch=new_branch_name, kind="InfraInterfaceL3", device__ids=[device1.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )
    peer_intfs_dev2 = sorted(
        await client.filters(
            branch=new_branch_name, kind="InfraInterfaceL3", device__ids=[device2.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )

    # Querying the object for now, need to pull from the store instead
    peer_ip = await client.create(
        branch=new_branch_name,
        kind="IpamIPAddress",
        interface={"id": peer_intfs_dev1[0].id},
        address=f"{str(next(new_peer_network))}/31",
    )
    await peer_ip.save()
    log.info(f" - Replaced {device1_name}-{peer_intfs_dev1[0].name.value} IP to {peer_ip.address.value}")

    ip = await client.create(
        branch=new_branch_name,
        kind="IpamIPAddress",
        interface={"id": peer_intfs_dev2[0].id},  # , "source": account_pop.id},
        address={"value": f"{str(next(new_peer_network))}/31"},  # , "source": account_pop.id},
    )
    await ip.save()
    log.info(f" - Replaced {device2_name}-{peer_intfs_dev2[0].name.value} IP to {ip.address.value}")


async def branch_scenario_remove_colt(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new Branch and Delete Colt Upstream Circuit
    """
    log.info("Create a new Branch and Delete Colt Upstream Circuit")
    new_branch_name = f"{site_name}-delete-upstream"
    new_branch = await client.branch.create(
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
        circuit_endpoint = await client.get(branch=new_branch_name, kind="InfraCircuitEndpoint", id=item["node"]["id"])
        await circuit_endpoint.delete()

        circuit = await client.get(
            branch=new_branch_name, kind="InfraCircuit", id=item["node"]["circuit"]["node"]["id"]
        )
        await circuit.delete()
        log.info(f" - Deleted Colt Technology Services [{circuit_id}]")


async def branch_scenario_conflict_device(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new Branch and introduce some conflicts
    """
    log.info("Create a new Branch and introduce some conflicts")
    device1_name = f"{site_name}-edge1"
    f"{site_name}-edge2"

    new_branch_name = f"{site_name}-maintenance-conflict"
    new_branch = await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Put {device1_name} in maintenance mode",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    maintenance_status = "maintenance"
    provisioning_status = "provisioning"
    drained_status = "drained"

    # Update Device 1 Status both in the Branch and in Main
    device1_branch = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device1_name)

    device1_branch.status.value = maintenance_status
    await device1_branch.save()

    intf1_branch = await client.get(
        branch=new_branch_name, kind="InfraInterfaceL3", device__ids=[device1_branch.id], name__value="Ethernet1"
    )
    intf1_branch.enabled.value = False
    intf1_branch.status.value = drained_status
    await intf1_branch.save()

    device1_main = await client.get(kind="InfraDevice", name__value=device1_name)

    device1_main.status.value = provisioning_status
    await device1_main.save()

    intf1_main = await client.get(kind="InfraInterfaceL3", device__ids=[device1_branch.id], name__value="Ethernet1")
    intf1_main.enabled.value = False
    await intf1_main.save()


async def branch_scenario_conflict_platform(client: InfrahubClient, log: logging.Logger):
    """
    Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE
    """
    log.info("Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE")
    new_branch_name = f"platform-conflict"
    new_branch = await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Add new platform",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    # Create a new Platform object with the same name, both in the branch and in main
    platform1_branch = await client.create(
        branch=new_branch_name, kind="InfraPlatform", name="Cisco IOS XR", netmiko_device_type="cisco_xr"
    )
    await platform1_branch.save()
    platform1_main = await client.create(kind="InfraPlatform", name="Cisco IOS XR", netmiko_device_type="cisco_xr")
    await platform1_main.save()

    # Delete an existing Platform object on both in the Branch and in Main
    platform2_branch = await client.get(branch=new_branch_name, kind="InfraPlatform", name__value="Cisco NXOS SSH")
    await platform2_branch.delete()
    platform2_main = await client.get(kind="InfraPlatform", name__value="Cisco NXOS SSH")
    await platform2_main.delete()

    # Delete an existing Platform object in the branch and update it in main
    platform3_branch = await client.get(branch=new_branch_name, kind="InfraPlatform", name__value="Juniper JunOS")
    await platform3_branch.delete()
    platform3_main = await client.get(kind="InfraPlatform", name__value="Juniper JunOS")
    platform3_main.nornir_platform.value = "juniper_junos"
    await platform3_main.save()


async def generate_continents_countries(client: InfrahubClient, log: logging.Logger, branch: str):
    for continent, countries in CONTINENT_COUNTRIES.items():
        continent_obj = await client.create(branch=branch, kind="LocationContinent", data={"name": continent})
        await continent_obj.save()
        store.set(key=continent, node=continent_obj)

        for country in countries:
            country_obj = await client.create(
                branch=branch, kind="LocationCountry", data={"name": country, "parent": continent_obj}
            )
            await country_obj.save()
            store.set(key=country, node=country_obj)


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    # ------------------------------------------
    # Create Continents, Countries
    # ------------------------------------------
    batch = await client.create_batch()
    batch.add(task=generate_continents_countries, client=client, branch=branch, log=log)
    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")
    # ------------------------------------------
    # Create User Accounts, Groups, Organizations & Platforms
    # ------------------------------------------
    log.info(f"Creating User Accounts, Groups & Organizations & Platforms")
    for account in ACCOUNTS:
        try:
            obj = await client.create(
                branch=branch,
                kind="CoreAccount",
                data={"name": account[0], "password": account[2], "type": account[1], "role": account[3]},
            )
            await obj.save()
        except GraphQLError:
            pass
        store.set(key=account[0], node=obj)
        log.info(f"- Created {obj._schema.kind} - {obj.name.value}")

    account_pop = store.get("pop-builder")
    account_chloe = store.get("Chloe O'Brian")
    account_crm = store.get("CRM Synchronization")

    batch = await client.create_batch()
    for group in GROUPS:
        obj = await client.create(branch=branch, kind="CoreStandardGroup", data={"name": group[0], "label": group[1]})

        batch.add(task=obj.save, node=obj)
        store.set(key=group[0], node=obj)

    for org in ORGANIZATIONS:
        data_org = {
            "name": {"value": org[0], "is_protected": True},
        }
        obj = await client.create(branch=branch, kind=f"Organization{org[1].title()}", data=data_org)
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)
    async for node, _ in batch.execute():
        accessor = f"{node._schema.default_filter.split('__')[0]}"
        log.info(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

    # Autonomous System
    organizations_dict = {name: type for name, type in ORGANIZATIONS}
    batch = await client.create_batch()
    for asn in ASNS:
        organization_type = organizations_dict.get(asn[1], None)
        asn_name = f"AS{asn[0]}"
        data_asn = {
            "name": {"value": asn_name, "source": account_crm.id, "owner": account_chloe.id},
            "asn": {"value": asn[0], "source": account_crm.id, "owner": account_chloe.id},
        }
        if organization_type:
            data_asn["description"] = {
                "value": f"{asn_name} for {asn[1]}",
                "source": account_crm.id,
                "owner": account_chloe.id,
            }
            data_asn["organization"] = {
                "id": store.get(kind=f"Organization{organization_type.title()}", key=asn[1]).id,
                "source": account_crm.id,
            }
        else:
            data_asn["description"] = {"value": f"{asn_name}", "source": account_crm.id, "owner": account_chloe.id}
        obj = await client.create(branch=branch, kind="InfraAutonomousSystem", data=data_asn)
        batch.add(task=obj.save, node=obj)
        store.set(key=asn[1], node=obj)

    for platform in PLATFORMS:
        obj = await client.create(
            branch=branch,
            kind="InfraPlatform",
            data={
                "name": platform[0],
                "nornir_platform": platform[1],
                "napalm_driver": platform[2],
                "netmiko_device_type": platform[3],
                "ansible_network_os": platform[4],
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=platform[0], node=obj)

    async for node, _ in batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    # ------------------------------------------
    # Create BGP Peer Groups
    # ------------------------------------------
    log.info(f"Creating BGP Peer Groups")
    batch = await client.create_batch()
    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        local_as_id = None
        local_as = store.get(kind="InfraAutonomousSystem", key=peer_group[3], raise_when_missing=False)
        remote_as = store.get(kind="InfraAutonomousSystem", key=peer_group[4], raise_when_missing=False)
        if remote_as:
            remote_as_id = remote_as.id
        if local_as:
            local_as_id = local_as.id

        obj = await client.create(
            branch=branch,
            kind="InfraBGPPeerGroup",
            name={"value": peer_group[0], "source": account_pop.id},
            import_policies={"value": peer_group[1], "source": account_pop.id},
            export_policies={"value": peer_group[2], "source": account_pop.id},
            local_as={"id": local_as_id},
            remote_as={"id": remote_as_id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=peer_group[0], node=obj)

    async for node, _ in batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    # ------------------------------------------
    # Create Tags
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Tags")
    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    async for node, _ in batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    internal_as = store.get(kind="InfraAutonomousSystem", key="Duff")

    # ------------------------------------------
    # Create IP prefixes
    # ------------------------------------------
    log.info("Creating IP Prefixes")
    for network in [
        NETWORKS_SUPERNET,
        MANAGEMENT_NETWORKS,
        NETWORKS_POOL_INTERNAL[0],
        NETWORKS_POOL_INTERNAL[1],
        NETWORKS_POOL_INTERNAL[2],
        NETWORKS_POOL_EXTERNAL_SUPERNET,
        NETWORKS_SUPERNET_IPV6,
        NETWORKS_POOL_INTERNAL_IPV6[4],
        NETWORKS_POOL_INTERNAL_IPV6[5],
    ]:
        obj = await client.create(branch=branch, kind="IpamIPPrefix", prefix=str(network), member_type="prefix")
        await obj.save()
    # ------------------------------------------
    # Create Pool IPv6 prefixes
    # ------------------------------------------
    log.info("Creating pool IPv6 Prefixes and IPs")
    for network in [
        NETWORKS_POOL_INTERNAL_IPV6[0],
        NETWORKS_POOL_INTERNAL_IPV6[1],
        NETWORKS_POOL_INTERNAL_IPV6[2],
        NETWORKS_POOL_INTERNAL_IPV6[3],
    ]:
        obj = await client.create(
            branch=branch, kind="IpamIPPrefix", is_pool=True, prefix=str(network), member_type="address"
        )
        await obj.save()
    log.debug(f"IP Prefixes Creation Completed")
    # ------------------------------------------
    # Create IPv6 IP from IPv6 Prefix pool
    # ------------------------------------------
    ipv6_addresses = []
    for network in NETWORKS_POOL_INTERNAL_IPV6[:4]:
        host_list = list(network.hosts())
        random_size = random.randint(0, len(host_list))
        ipv6_addresses.extend(host_list[:random_size])

    batch = await client.create_batch()
    for ipv6_addr in ipv6_addresses:
        obj = await client.create(
            branch=branch,
            kind="IpamIPAddress",
            address={"value": ipv6_addr, "source": account_pop.id},
        )
        batch.add(task=obj.save, node=obj)

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")

    # ------------------------------------------
    # Create Profiles
    # ------------------------------------------
    for intf_profile in INTERFACE_PROFILES:
        data_profile = {
            "profile_name": {"value": intf_profile[0]},
            "mtu": {"value": intf_profile[1]},
        }
        profile = await client.create(branch=branch, kind=f"Profile{intf_profile[2]}", data=data_profile)
        await profile.save()
        store.set(key=intf_profile[0], node=profile)

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site and associated objects (Device, Circuit, BGP Sessions)")
    sites = site_generator(nbr_site=5)
    batch = await client.create_batch()
    for site in sites:
        batch.add(task=generate_site, site=site, client=client, branch=branch, log=log)

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")

    # ------------------------------------------
    # Add profile on interfaces upstream/backbone
    # ------------------------------------------
    # FIXME - Could do it better
    upstream_interfaces = await client.filters(branch=branch, kind="InfraInterfaceL3", role__value="upstream")
    backbone_interfaces = await client.filters(branch=branch, kind="InfraInterfaceL3", role__value="backbone")
    for interface in upstream_interfaces:
        profile_id = store.get(key="upstream_profile", kind="ProfileInfraInterfaceL3").id
        await interface.profiles.fetch()
        interface.profiles.add(profile_id)
        await interface.save()
    for interface in backbone_interfaces:
        profile_id = store.get(key="backbone_profile", kind="ProfileInfraInterfaceL3").id
        await interface.profiles.fetch()
        interface.profiles.add(profile_id)
        await interface.save()

    # --------------------------------------------------
    # CREATE Full Mesh iBGP SESSION between all the Edge devices
    # --------------------------------------------------
    log.info("Creating Full Mesh iBGP SESSION between all the Edge devices")
    batch = await client.create_batch()
    for site1 in sites:
        for site2 in sites:
            if site1 == site2:
                continue

            for idx1 in range(1, 3):
                for idx2 in range(1, 3):
                    device1 = f"{site1['name']}-edge{idx1}"
                    device2 = f"{site2['name']}-edge{idx2}"

                    loopback1 = store.get(key=f"{device1}-loopback")
                    loopback2 = store.get(key=f"{device2}-loopback")

                    peer_group_name = "POP_GLOBAL"

                    obj = await client.create(
                        branch=branch,
                        kind="InfraBGPSession",
                        type="INTERNAL",
                        local_as=internal_as.id,
                        local_ip=loopback1.id,
                        remote_as=internal_as.id,
                        remote_ip=loopback2.id,
                        peer_group=store.get(key=peer_group_name).id,
                        device=store.get(kind="InfraDevice", key=device1).id,
                        status=ACTIVE_STATUS,
                        role=BACKBONE_ROLE,
                    )
                    batch.add(task=obj.save, node=obj)

    async for node, _ in batch.execute():
        if node._schema.default_filter:
            accessor = f"{node._schema.default_filter.split('__')[0]}"
            log.info(f"{node._schema.kind} {getattr(node, accessor).value} - Creation Completed")
        else:
            log.info(f"{node} - Creation Completed")

    # --------------------------------------------------
    # CREATE Backbone Links & Circuits
    # --------------------------------------------------
    log.info("Creating Backbone Links & Circuits")
    for idx, backbone_link in enumerate(P2P_NETWORKS_POOL.keys()):
        site1 = backbone_link[0]
        site2 = backbone_link[2]
        device = backbone_link[1]

        intf1 = INTERFACE_OBJS[f"{site1}-{device}"].pop(0)
        intf2 = INTERFACE_OBJS[f"{site2}-{device}"].pop(0)

        circuit_id = BACKBONE_CIRCUIT_IDS[idx]

        if idx <= 2:
            provider_name = "Lumen"
        else:
            provider_name = "Zayo"

        provider = store.get(kind="OrganizationProvider", key=provider_name)
        obj = await client.create(
            branch=branch,
            kind="InfraCircuit",
            description=f"Backbone {site1} <-> {site2}",
            circuit_id=BACKBONE_CIRCUIT_IDS[idx],
            vendor_id=f"{provider_name.upper()}-{UUIDT().short()}",
            provider=provider,
            # type="DARK FIBER",
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        await obj.save()
        log.info(f"- Created {obj._schema.kind} - {provider_name} [{obj.vendor_id.value}]")

        # Create Circuit Endpoints
        endpoint1 = await client.create(
            branch=branch,
            kind="InfraCircuitEndpoint",
            description=f"Endpoint {circuit_id} to {site1}-{device}",
            site=site1,
            circuit=obj,
            connected_endpoint=intf1,
        )
        await endpoint1.save()

        endpoint2 = await client.create(
            branch=branch,
            kind="InfraCircuitEndpoint",
            description=f"Endpoint {circuit_id} to {site2}-{device}",
            site=site2,
            circuit=obj,
            connected_endpoint=intf2,
        )
        await endpoint2.save()

        # Create IP Address
        intf11_address = f"{str(next(P2P_NETWORKS_POOL[backbone_link]))}/31"
        intf21_address = f"{str(next(P2P_NETWORKS_POOL[backbone_link]))}/31"
        intf11_ip = await client.create(
            branch=branch,
            kind="IpamIPAddress",
            interface={"id": intf1.id, "source": account_pop.id},
            address={"value": intf11_address, "source": account_pop.id},
        )
        await intf11_ip.save()
        intf21_ip = await client.create(
            branch=branch,
            kind="IpamIPAddress",
            interface={"id": intf2.id, "source": account_pop.id},
            address={"value": intf21_address, "source": account_pop.id},
        )
        await intf21_ip.save()

        # Update Interface
        intf11 = await client.get(branch=branch, kind="InfraInterfaceL3", id=intf1.id)
        intf11.description.value = f"Backbone: Connected to {site2}-{device} via {circuit_id}"
        await intf11.save()

        intf21 = await client.get(branch=branch, kind="InfraInterfaceL3", id=intf2.id)
        intf21.description.value = f"Backbone: Connected to {site1}-{device} via {circuit_id}"
        await intf21.save()

        log.info(f" - Connected '{site1}-{device}::{intf1.name.value}' <> '{site2}-{device}::{intf2.name.value}'")

    # --------------------------------------------------
    # Create some changes in additional branches
    #  Scenario 1 - Add a Peering
    #  Scenario 2 - Change the IP Address between 2 edges
    #  Scenario 3 - Delete a Circuit + Peering
    #  Scenario 4 - Create some Relationship One and Attribute conflicts on a device
    #  Scenario 5 - Create some Node ADD and DELETE conflicts on some platform objects
    # --------------------------------------------------
    if branch == "main":
        await branch_scenario_add_upstream(
            site_name=sites[1]["name"],
            client=client,
            log=log,
        )
        await branch_scenario_replace_ip_addresses(site_name=sites[2]["name"], client=client, log=log)
        await branch_scenario_remove_colt(site_name=sites[0]["name"], client=client, log=log)
        await branch_scenario_conflict_device(site_name=sites[3]["name"], client=client, log=log)
        await branch_scenario_conflict_platform(client=client, log=log)
