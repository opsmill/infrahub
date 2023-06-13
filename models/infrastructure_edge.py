import logging
import uuid
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Dict, List

from infrahub_client import InfrahubClient, InfrahubNode, NodeStore

# flake8: noqa
# pylint: skip-file

DEVICE_ROLES = ["edge"]
INTF_ROLES = ["backbone", "transit", "peering", "peer", "loopback", "management", "spare"]
VLAN_ROLES = ["server"]

SITES = ["atl", "ord", "jfk", "den", "dfw", "iad", "bkk", "sfo", "iah", "mco"]

PLATFORMS = (
    ("Cisco IOS", "ios", "ios", "cisco_ios", "ios"),
    ("Cisco NXOS SSH", "nxos_ssh", "nxos_ssh", "cisco_nxos", "nxos"),
    ("Juniper JunOS", "junos", "junos", "juniper_junos", "junos"),
)

DEVICES = (
    ("edge1", "active", "7280R3", "profile1", "edge", ["red", "green"], "Juniper JunOS"),
    ("edge2", "active", "ASR1002-HX", "profile1", "edge", ["red", "blue", "green"], "Cisco IOS"),
)


NETWORKS_POOL_INTERNAL = IPv4Network("10.0.0.0/8").subnets(new_prefix=16)
LOOPBACK_POOL = next(NETWORKS_POOL_INTERNAL).hosts()
P2P_NETWORK_POOL = next(NETWORKS_POOL_INTERNAL).subnets(new_prefix=31)
NETWORKS_POOL_EXTERNAL = IPv4Network("203.0.113.0/24").subnets(new_prefix=29)

MANAGEMENT_IPS = IPv4Network("172.20.20.16/28").hosts()


def site_names_generator(nbr_site=2) -> List[str]:
    """Generate a list of site names by iterating over the list of SITES defined above and by increasing the id.

    site_names_generator(nbr_site=5)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1"]

    site_names_generator(nbr_site=12)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1", "iad1", "bkk1", "sfo1", "iah1", "mco1", "atl2", "ord2"]
    """

    site_names: List[str] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        site_names.extend([f"{site}{idx}" for site in SITES[:nbr_this_loop]])

    return site_names


# P2P_NETWORKS_POOL = {
#     ("atl1", "edge1", "ord1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
#     ("atl1", "edge1", "jfk1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
#     ("jfk1", "edge1", "ord1", "edge1"): next(P2P_NETWORK_POOL).hosts(),
#     ("atl1", "edge2", "ord1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
#     ("atl1", "edge2", "jfk1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
#     ("jfk1", "edge2", "ord1", "edge2"): next(P2P_NETWORK_POOL).hosts(),
# }

BACKBONE_CIRCUIT_IDS = [
    "DUFF-1543451",
    "DUFF-6535773",
    "DUFF-5826854",
    "DUFF-8263953",
    "DUFF-7324064",
    "DUFF-4867430",
    "DUFF-4654456",
]

INTERFACE_MGMT_NAME = {"7280R3": "Management0", "ASR1002-HX": "Management0"}

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
}
INTERFACE_L2_NAMES = {
    "7280R3": ["Ethernet11", "Ethernet12"],
    "ASR1002-HX": ["Ethernet11", "Ethernet12"],
}

INTERFACE_ROLES_MAPPING = {
    "edge": [
        "peer",
        "peer",
        "backbone",
        "backbone",
        "transit",
        "transit",
        "spare",
        "spare",
        "peering",
        "spare",
        "spare",
        "spare",
    ],
}

STATUSES = ["active", "provisionning", "maintenance", "drained"]

TAGS = ["blue", "green", "red"]

ORGANIZATIONS = (
    ["Telia", 1299],
    ["Colt", 8220],
    ["Verizon", 701],
    ["GTT", 3257],
    ["Hurricane Electric", 6939],
    ["Lumen", 3356],
    ["Zayo", 6461],
    ["Duff", 64496],
    ["Equinix", 24115],
)

INTERFACE_OBJS: Dict[str, List[InfrahubNode]] = defaultdict(list)

ACCOUNTS = (
    ("pop-builder", "Script", "Password123"),
    ("CRM Synchronization", "Script", "Password123"),
    ("Jack Bauer", "User", "Password123"),
    ("Chloe O'Brian", "User", "Password123"),
    ("David Palmer", "User", "Password123"),
)

ACCOUNT_GROUPS = (
    ("network_operation", "Operation Team"),
    ("network_engineering", "Engineering Team"),
    ("network_architecture", "Architecture Team"),
)

BGP_PEER_GROUPS = (
    ("POP_INTERNAL", "IMPORT_INTRA_POP", "EXPORT_INTRA_POP", "Duff", "Duff"),
    ("POP_GLOBAL", "IMPORT_POP_GLOBAL", "EXPORT_POP_GLOBLA", "Duff", None),
    ("TRANSIT_DEFAULT", "IMPORT_TRANSIT", "EXPORT_PUBLIC_PREFIX", "Duff", None),
    ("TRANSIT_TELIA", "IMPORT_TRANSIT", "EXPORT_PUBLIC_PREFIX", "Duff", "Telia"),
    ("IX_DEFAULT", "IMPORT_IX", "EXPORT_PUBLIC_PREFIX", "Duff", None),
)

VLANS = (
    ("200", "server"),
    ("400", "management"),
)

store = NodeStore()


async def generate_site(client: InfrahubClient, log: logging.Logger, branch: str, site_name: str):
    group_eng = store.get("network_engineering")
    group_ops = store.get("network_operation")
    account_pop = store.get("pop-builder")
    # store.get("Chloe O'Brian")
    account_crm = store.get("CRM Synchronization")
    active_status = store.get(kind="Status", key="active")
    internal_as = store.get(kind="AutonomousSystem", key="Duff")

    # --------------------------------------------------
    # Create the Site
    # --------------------------------------------------
    site = await client.create(
        branch=branch,
        kind="Location",
        name={"value": site_name, "is_protected": True, "source": account_crm.id},
        type={"value": "SITE", "is_protected": True, "source": account_crm.id},
    )
    await site.save()
    log.info(f"Created Site: {site_name}")

    peer_networks = {
        0: next(P2P_NETWORK_POOL).hosts(),
        1: next(P2P_NETWORK_POOL).hosts(),
    }

    # --------------------------------------------------
    # Create the site specific VLAN
    # --------------------------------------------------
    for vlan in VLANS:
        status_id = active_status.id
        role_id = store.get(kind="Role", key=vlan[1]).id
        vlan_name = f"{site_name}_{vlan[1]}"
        obj = await client.create(
            branch=branch,
            kind="VLAN",
            name={"value": f"{site_name}_{vlan[1]}", "is_protected": True, "source": account_pop.id},
            vlan_id={"value": int(vlan[0]), "is_protected": True, "owner": group_eng.id, "source": account_pop.id},
            status={"id": status_id, "owner": group_ops.id},
            role={"id": role_id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
        )
        await obj.save()

        store.set(key=vlan_name, node=obj)

    for idx, device in enumerate(DEVICES):
        device_name = f"{site_name}-{device[0]}"
        status_id = store.get(kind="Status", key=device[1]).id
        role_id = store.get(kind="Role", key=device[4]).id
        device_type = device[2]
        platform_id = store.get(kind="Platform", key=device[6]).id

        obj = await client.create(
            branch=branch,
            kind="Device",
            site={"id": site.id, "source": account_pop.id, "is_protected": True},
            name={"value": device_name, "source": account_pop.id, "is_protected": True},
            status={"id": status_id, "owner": group_ops.id},
            type={"value": device[2], "source": account_pop.id},
            role={"id": role_id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            asn={"id": internal_as.id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            tags=[store.get(kind="Tag", key=tag_name).id for tag_name in device[5]],
            platform={"id": platform_id, "source": account_pop.id, "is_protected": True},
        )
        await obj.save()

        store.set(key=device_name, node=obj)
        log.info(f"- Created Device: {device_name}")

        # Loopback Interface
        intf = await client.create(
            branch=branch,
            kind="InterfaceL3",
            device={"id": obj.id, "is_protected": True},
            name={"value": "Loopback0", "source": account_pop.id, "is_protected": True},
            enabled=True,
            status={"id": active_status.id, "owner": group_ops.id},
            role={"id": store.get(kind="Role", key="loopback").id, "source": account_pop.id, "is_protected": True},
            speed=1000,
        )
        await intf.save()

        ip = await client.create(
            branch=branch,
            kind="IPAddress",
            interface={"id": intf.id, "source": account_pop.id},
            address={"value": f"{str(next(LOOPBACK_POOL))}/32", "source": account_pop.id},
        )
        await ip.save()

        store.set(key=f"{device_name}-loopback", node=ip)

        # Management Interface
        intf = await client.create(
            branch=branch,
            kind="InterfaceL3",
            device={"id": obj.id, "is_protected": True},
            name={"value": INTERFACE_MGMT_NAME[device_type], "source": account_pop.id},
            enabled={"value": True, "owner": group_eng.id},
            status={"id": active_status.id, "owner": group_eng.id},
            role={"id": store.get(kind="Role", key="management").id, "source": account_pop.id, "is_protected": True},
            speed=1000,
        )
        await intf.save()

        ip = await client.create(
            branch=branch, kind="IPAddress", interface=intf.id, address=f"{str(next(MANAGEMENT_IPS))}/24"
        )
        await ip.save()

        # set the IP address of the device to the management interface IP address
        obj.primary_address = ip
        await obj.save()

        # L3 Interfaces
        for intf_idx, intf_name in enumerate(INTERFACE_L3_NAMES[device_type]):
            intf_role = INTERFACE_ROLES_MAPPING[device[4]][intf_idx]
            intf_role_id = store.get(kind="Role", key=intf_role).id

            intf = await client.create(
                branch=branch,
                kind="InterfaceL3",
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"id": active_status.id, "owner": group_ops.id},
                role={"id": intf_role_id, "source": account_pop.id},
            )
            await intf.save()

            store.set(key=f"{device_name}-l3-{intf_idx}", node=intf)
            INTERFACE_OBJS[device_name].append(intf)

            address = None
            if intf_role == "peer":
                address = f"{str(next(peer_networks[intf_idx]))}/31"

            # if intf_role == "backbone":
            #     site_idx = intf_idx - 2
            #     other_site_name = other_sites[site_idx]
            #     sites = sorted([site_name, other_site_name])
            #     link_id = (sites[0], device[0], sites[1], device[0])
            #     address = f"{str(next(P2P_NETWORKS_POOL[link_id]))}/31"

            if intf_role in ["transit", "peering"]:
                subnet = next(NETWORKS_POOL_EXTERNAL).hosts()
                address = f"{str(next(subnet))}/29"
                peer_address = f"{str(next(subnet))}/29"

            if not address:
                continue

            if address:
                ip = await client.create(
                    branch=branch,
                    kind="IPAddress",
                    interface={"id": intf.id, "source": account_pop.id},
                    address={"value": address, "source": account_pop.id},
                )
                await ip.save()

            # Create Circuit and BGP session for transit and peering
            if intf_role in ["transit", "peering"]:
                circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-{intf_role}-{address}"))))[24:]
                circuit_id = f"DUFF-{circuit_id_unique}"
                transit_providers = ["Telia", "Colt"]

                if intf_role == "transit":
                    provider_name = transit_providers[intf_idx % 2]
                elif intf_role == "peering":
                    provider_name = "Equinix"

                provider = store.get(kind="Organization", key=provider_name)

                circuit = await client.create(
                    branch=branch,
                    kind="Circuit",
                    circuit_id=circuit_id,
                    vendor_id=f"{provider_name.upper()}-{str(uuid.uuid4())[:8]}",
                    provider=provider.id,
                    status={"id": active_status.id, "owner": group_ops.id},
                    role={
                        "id": store.get(kind="Role", key=intf_role).id,
                        "source": account_pop.id,
                        "owner": group_eng.id,
                    },
                )
                await circuit.save()

                endpoint1 = await client.create(
                    branch=branch,
                    kind="CircuitEndpoint",
                    site=site,
                    circuit=circuit.id,
                    connected_interface=intf.id,
                )
                await endpoint1.save()

                intf.description.value = f"Connected to {provider_name} via {circuit_id}"

                if intf_role == "transit":
                    peer_group_name = "TRANSIT_TELIA" if "telia" in provider.name.value.lower() else "TRANSIT_DEFAULT"

                    peer_ip = await client.create(
                        branch=branch,
                        kind="IPAddress",
                        address=peer_address,
                    )
                    await peer_ip.save()

                    peer_as = store.get(kind="AutonomousSystem", key=provider_name)
                    bgp_session = await client.create(
                        branch=branch,
                        kind="BGPSession",
                        type="EXTERNAL",
                        local_as=internal_as.id,
                        local_ip=ip.id,
                        remote_as=peer_as.id,
                        remote_ip=peer_ip.id,
                        peer_group=store.get(key=peer_group_name).id,
                        device=store.get(key=device_name).id,
                        status=active_status.id,
                        role=store.get(kind="Role", key=intf_role).id,
                    )
                    await bgp_session.save()

                    log.info(
                        f" Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                    )

        # L2 Interfaces
        for intf_idx, intf_name in enumerate(INTERFACE_L2_NAMES[device_type]):
            intf_role_id = store.get(kind="Role", key="server").id

            intf = await client.create(
                branch=branch,
                kind="InterfaceL2",
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"id": active_status.id, "owner": group_ops.id},
                role={"id": intf_role_id, "source": account_pop.id},
                l2_mode="Access",
                untagged_vlan={"id": store.get(kind="VLAN", key=f"{site_name}_server").id},
            )
            await intf.save()

    # --------------------------------------------------
    # Connect both devices within the Site together with 2 interfaces
    # --------------------------------------------------
    for idx in range(0, 2):
        intf1 = store.get(kind="InterfaceL3", key=f"{site_name}-edge1-l3-{idx}")
        intf2 = store.get(kind="InterfaceL3", key=f"{site_name}-edge2-l3-{idx}")

        # intf1.connected_endpoint.add(intf2)
        intf1.description.value = f"Connected to {site_name}-edge2 {intf2.name.value}"
        await intf1.save()

        intf2.description.value = f"Connected to {site_name}-edge1 {intf1.name.value}"
        await intf2.save()

        log.info(f"Connected  '{site_name}-edge1::{intf1.name.value}' <> '{site_name}-edge2::{intf2.name.value}'")

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
            kind="BGPSession",
            type="INTERNAL",
            local_as=internal_as.id,
            local_ip=loopback1.id,
            remote_as=internal_as.id,
            remote_ip=loopback2.id,
            peer_group=store.get(key=peer_group_name).id,
            device=store.get(kind="Device", key=device1).id,
            status=active_status.id,
            role=store.get(kind="Role", key="backbone").id,
        )
        await obj.save()

        log.info(
            f" Created BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
        )

    return site_name


async def branch_scenario_add_transit(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new branch and Add a new transit link with GTT on the edge1 device of the given site.
    """
    device_name = f"{site_name}-edge1"

    new_branch_name = f"{site_name}-add-transit"
    new_branch = await client.branch.create(
        branch_name=new_branch_name, data_only=True, description=f"Add a new Transit link in {site_name}"
    )
    log.info(f"Created branch: {new_branch_name!r}")

    # Querying the object for now, need to pull from the store instead
    site = await client.get(branch=new_branch_name, kind="Location", name__value=site_name)

    device = await client.get(branch=new_branch_name, kind="Device", name__value=device_name)
    active_status = await client.get(branch=new_branch_name, kind="Status", name__value="active")
    role_transit = await client.get(branch=new_branch_name, kind="Role", name__value="transit")
    role_spare = await client.get(branch=new_branch_name, kind="Role", name__value="spare")
    gtt_organization = await client.get(branch=new_branch_name, kind="Organization", name__value="GTT")

    store.set(key="active", node=active_status)
    store.set(key="transit", node=role_transit)
    store.set(key="GTT", node=gtt_organization)

    intfs = await client.filters(
        branch=new_branch_name, kind="InterfaceL3", device__id=device.id, role__id=role_spare.id
    )
    intf = intfs[0]
    log.info(f" Adding new Transit on '{device_name}::{intf.name.value}'")

    # Allocate a new subnet and calculate new IP Addresses
    subnet = next(NETWORKS_POOL_EXTERNAL).hosts()
    address = f"{str(next(subnet))}/29"
    peer_address = f"{str(next(subnet))}/29"

    peer_ip = await client.create(
        branch=new_branch_name,
        kind="IPAddress",
        address=peer_address,
    )
    await peer_ip.save()

    ip = await client.create(
        branch=new_branch_name,
        kind="IPAddress",
        interface={"id": intf.id},
        address={"value": address},
    )
    await ip.save()

    provider = store.get(kind="Organization", key="GTT")
    circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-transit-{address}"))))[24:]
    circuit_id = f"DUFF-{circuit_id_unique}"

    circuit = await client.create(
        branch=new_branch_name,
        kind="Circuit",
        circuit_id=circuit_id,
        vendor_id=f"{provider.name.value.upper()}-{str(uuid.uuid4())[:8]}",
        provider=provider.id,
        status={"id": active_status.id},  # "owner": group_ops.id},
        role={
            "id": store.get(kind="Role", key="transit").id,
            # "source": account_pop.id,
            # "owner": group_eng.id,
        },
    )
    await circuit.save()

    endpoint1 = await client.create(
        branch=new_branch_name,
        kind="CircuitEndpoint",
        site=site,
        circuit=circuit.id,
        connected_interface=intf.id,
    )
    await endpoint1.save()

    intf.description.value = f"Connected to {provider.name.value} via {circuit_id}"
    await intf.save()

    # Create BGP Session

    # Create Circuit
    # Create IP address
    # Change Role
    # Change description

    # peer_group_name = "TRANSIT_DEFAULT"

    #     peer_as = store.get(kind="AutonomousSystem", key=provider_name)
    #     bgp_session = await client.create(
    #         branch=branch,
    #         kind="BGPSession",
    #         type="EXTERNAL",
    #         local_as=internal_as.id,
    #         local_ip=ip.id,
    #         remote_as=peer_as.id,
    #         remote_ip=peer_ip.id,
    #         peer_group=store.get(key=peer_group_name).id,
    #         device=store.get(key=device_name).id,
    #         status=active_status.id,
    #         role=store.get(kind="Role", key=intf_role).id,
    #     )
    #     await bgp_session.save()

    #     log.info(
    #         f" Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
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
        data_only=True,
        description=f"Change the IP addresses between edge1 and edge2 in {site_name}",
    )
    log.info(f"Created branch: {new_branch_name!r}")

    new_peer_network = next(P2P_NETWORK_POOL).hosts()

    # site = await client.get(branch=new_branch_name, kind="Location", name__value=site_name)
    device1 = await client.get(branch=new_branch_name, kind="Device", name__value=device1_name)
    device2 = await client.get(branch=new_branch_name, kind="Device", name__value=device2_name)
    role_peer = await client.get(branch=new_branch_name, kind="Role", name__value="peer")

    peer_intfs_dev1 = sorted(
        await client.filters(branch=new_branch_name, kind="InterfaceL3", device__id=device1.id, role__id=role_peer.id),
        key=lambda x: x.name.value,
    )
    peer_intfs_dev2 = sorted(
        await client.filters(branch=new_branch_name, kind="InterfaceL3", device__id=device2.id, role__id=role_peer.id),
        key=lambda x: x.name.value,
    )

    # Querying the object for now, need to pull from the store instead
    peer_ip = await client.create(
        branch=new_branch_name,
        kind="IPAddress",
        interface={"id": peer_intfs_dev1[0].id},
        address=f"{str(next(new_peer_network))}/31",
    )
    await peer_ip.save()

    ip = await client.create(
        branch=new_branch_name,
        kind="IPAddress",
        interface={"id": peer_intfs_dev2[0].id},  # , "source": account_pop.id},
        address={"value": f"{str(next(new_peer_network))}/31"},  # , "source": account_pop.id},
    )
    await ip.save()


async def branch_scenario_remove_colt(client: InfrahubClient, log: logging.Logger, site_name: str):
    """
    Create a new Branch and Delete both Transit Circuit with Colt
    """
    new_branch_name = f"{site_name}-delete-transit"
    new_branch = await client.branch.create(
        branch_name=new_branch_name, data_only=True, description=f"Delete transit circuit with colt in {site_name}"
    )
    log.info(f"Created branch: {new_branch_name!r}")

    spare = await client.get(branch=new_branch_name, kind="Role", name__value="peer")

    # TODO need to update the role on the interface and need to delete the IP Address
    # for idx in range(1, 3):
    #     device_name = f"{site_name}-edge{idx}"
    #     device = await client.get(branch=new_branch_name, kind="Device", name__value=device_name)
    #     intf = await client.get(branch=new_branch_name, kind="InterfaceL3", device__id=device.id, name__value="Ethernet5")

    # Delete circuits
    get_circuits_query = """
    query($site_name: String!) {
        circuit_endpoint(site__name__value: $site_name) {
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
        for circuit in circuits["circuit_endpoint"]["edges"]
        if circuit["node"]["circuit"]["node"]["provider"]["node"]["name"]["value"] == "Colt"
    ]

    for item in colt_circuits:
        circuit_endpoint = await client.get(branch=new_branch_name, kind="CircuitEndpoint", id=item["node"]["id"])
        await circuit_endpoint.delete()

        circuit = await client.get(branch=new_branch_name, kind="Circuit", id=item["node"]["circuit"]["node"]["id"])
        await circuit.delete()


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    SITE_NAMES = site_names_generator(nbr_site=5)

    # ------------------------------------------
    # Create User Accounts, Groups & Organizations & Platforms
    # ------------------------------------------
    batch = await client.create_batch()

    for group in ACCOUNT_GROUPS:
        obj = await client.create(branch=branch, kind="Group", data={"name": group[0], "label": group[1]})
        batch.add(task=obj.save, node=obj)
        store.set(key=group[0], node=obj)

    for account in ACCOUNTS:
        obj = await client.create(
            branch=branch, kind="Account", data={"name": account[0], "password": account[2], "type": account[1]}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=account[0], node=obj)

    for org in ORGANIZATIONS:
        obj = await client.create(
            branch=branch, kind="Organization", data={"name": {"value": org[0], "is_protected": True}}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)

    for platform in PLATFORMS:
        obj = await client.create(
            branch=branch,
            kind="Platform",
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

    # Create all Groups, Accounts and Organizations
    async for node, _ in batch.execute():
        log.info(f"{node._schema.kind} Created {node.name.value}")

    store.get("network_engineering")
    store.get("network_operation")
    account_pop = store.get("pop-builder")
    account_cloe = store.get("Chloe O'Brian")
    store.get("CRM Synchronization")

    # ------------------------------------------
    # Create Autonommous Systems
    # ------------------------------------------
    batch = await client.create_batch()
    for org in ORGANIZATIONS:
        obj = await client.create(
            branch=branch,
            kind="AutonomousSystem",
            data={
                "name": {"value": f"AS{org[1]}", "source": account_pop.id, "owner": account_cloe.id},
                "asn": {"value": org[1], "source": account_pop.id, "owner": account_cloe.id},
                "organization": {"id": store.get(kind="Organization", key=org[0]).id, "source": account_pop.id},
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)

    async for node, _ in batch.execute():
        log.info(f"{node._schema.kind} Created {node.name.value}")

    # ------------------------------------------
    # Create BGP Peer Groups
    # ------------------------------------------
    batch = await client.create_batch()
    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        remote_as = store.get(kind="AutonomousSystem", key=peer_group[4], raise_when_missing=False)
        if remote_as:
            remote_as_id = remote_as.id

        obj = await client.create(
            branch=branch,
            kind="BGPPeerGroup",
            name={"value": peer_group[0], "source": account_pop.id},
            import_policies={"value": peer_group[1], "source": account_pop.id},
            export_policies={"value": peer_group[2], "source": account_pop.id},
            local_as=store.get(kind="AutonomousSystem", key=peer_group[3]).id,
            remote_as=remote_as_id,
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=peer_group[0], node=obj)

    async for node, _ in batch.execute():
        log.info(f"Peer Group Created Created {node.name.value}")

    # ------------------------------------------
    # Create Status, Role & Tags
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Roles, Status & Tag")
    for role in DEVICE_ROLES + INTF_ROLES + VLAN_ROLES:
        obj = await client.create(branch=branch, kind="Role", name={"value": role, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=role, node=obj)

    for status in STATUSES:
        obj = await client.create(branch=branch, kind="Status", name={"value": status, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=status, node=obj)

    for tag in TAGS:
        obj = await client.create(branch=branch, kind="Tag", name={"value": tag, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    async for node, _ in batch.execute():
        log.info(f"{node._schema.kind}  Created {node.name.value}")

    active_status = store.get(kind="Status", key="active")
    internal_as = store.get(kind="AutonomousSystem", key="Duff")

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site & Device")

    batch = await client.create_batch()

    for site_name in SITE_NAMES:
        batch.add(task=generate_site, site_name=site_name, client=client, branch=branch, log=log)

    async for _, response in batch.execute():
        log.debug(f"Site {response} Creation Completed")

    # --------------------------------------------------
    # CREATE Full Mesh iBGP SESSION between all the Edge devices
    # --------------------------------------------------
    batch = await client.create_batch()
    for site1 in SITE_NAMES:
        for site2 in SITE_NAMES:
            if site1 == site2:
                continue

            for idx1 in range(1, 3):
                for idx2 in range(1, 3):
                    device1 = f"{site1}-edge{idx1}"
                    device2 = f"{site2}-edge{idx2}"

                    loopback1 = store.get(key=f"{device1}-loopback")
                    loopback2 = store.get(key=f"{device2}-loopback")

                    peer_group_name = "POP_GLOBAL"

                    obj = await client.create(
                        branch=branch,
                        kind="BGPSession",
                        type="INTERNAL",
                        local_as=internal_as.id,
                        local_ip=loopback1.id,
                        remote_as=internal_as.id,
                        remote_ip=loopback2.id,
                        peer_group=store.get(key=peer_group_name).id,
                        device=store.get(kind="Device", key=device1).id,
                        status=active_status.id,
                        role=store.get(kind="Role", key="backbone").id,
                    )
                    batch.add(task=obj.save, node=obj)
                    log.info(
                        f"Creating BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
                    )

    async for node, _ in batch.execute():
        log.debug(f"BGP Session Creation Completed")

    # --------------------------------------------------
    # CREATE BACKBONE LINKS & CIRCUITS
    # --------------------------------------------------
    # for idx, backbone_link in enumerate(P2P_NETWORKS_POOL.keys()):
    #     site1 = backbone_link[0]
    #     site2 = backbone_link[2]
    #     device = backbone_link[1]

    #     # Build a new list with the names of the other sites for later
    #     other_site_site1 = copy.copy(SITES)
    #     other_site_site1.remove(site1)
    #     other_site_site1 = sorted(other_site_site1)

    #     other_site_site2 = copy.copy(SITES)
    #     other_site_site2.remove(site2)
    #     other_site_site2 = sorted(other_site_site2)

    #     intf1 = INTERFACE_OBJS[f"{site1}-{device}"][other_site_site1.index(site2) + 2]
    #     intf2 = INTERFACE_OBJS[f"{site2}-{device}"][other_site_site2.index(site1) + 2]

    #     circuit_id = BACKBONE_CIRCUIT_IDS[idx]

    #     if idx <= 2:
    #         provider_name = "Lumen"
    #     else:
    #         provider_name = "Zayo"

    #     provider = store.get(kind="Organization", key=provider_name)
    #     obj = await client.create(
    #         branch=branch,
    #         kind="Circuit",
    #         circuit_id=BACKBONE_CIRCUIT_IDS[idx],
    #         vendor_id=f"{provider_name.upper()}-{str(uuid.uuid4())[:8]}",
    #         provider=provider,
    #         # type="DARK FIBER",
    #         status=active_status,
    #         role=store.get(kind="Role", key="backbone"),
    #     )
    #     await obj.save()

    #     endpoint1 = await client.create(
    #         branch=branch, kind="CircuitEndpoint", site=site1, circuit=obj, connected_endpoint=intf1
    #     )
    #     await endpoint1.save()
    #     endpoint2 = await client.create(
    #         branch=branch, kind="CircuitEndpoint", site=site2, circuit=obj, connected_endpoint=intf2
    #     )
    #     await endpoint2.save()

    #     intf11 = await client.get(branch=branch, kind="InterfaceL3", id=intf1.id)

    #     intf11.description.value = f"Connected to {site2}-{device} via {circuit_id}"
    #     await intf11.save()

    #     intf21 = await client.get(branch=branch, kind="InterfaceL3", id=intf2.id)
    #     intf21.description.value = f"Connected to {site1}-{device} via {circuit_id}"
    #     await intf21.save()

    #     log.info(f"Connected  '{site1}-{device}::{intf1.name.value}' <> '{site2}-{device}::{intf2.name.value}'")

    # --------------------------------------------------
    # Create some changes in additional branches
    #  Scenario 1 - Add a Peering
    #  Scenario 2 - Change the IP Address between 2 edges
    #  Scenario 3 - Delete a Circuit + Peering
    #  TODO branch4 - Create some conflicts
    #  TODO branch5 - Drain Site
    # --------------------------------------------------
    if branch == "main":
        await branch_scenario_add_transit(
            site_name=SITE_NAMES[1],
            client=client,
            log=log,
        )
        await branch_scenario_replace_ip_addresses(site_name=SITE_NAMES[2], client=client, log=log)
        await branch_scenario_remove_colt(site_name=SITE_NAMES[0], client=client, log=log)
