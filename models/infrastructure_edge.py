import copy
import logging
import uuid
from asyncio import run as aiorun
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Dict, List, Optional

import typer
from rich.logging import RichHandler

from infrahub_client import InfrahubClient, InfrahubNode, NodeStore

# flake8: noqa
# pylint: skip-file

DEVICE_ROLES = ["edge"]
INTF_ROLES = ["backbone", "transit", "peering", "peer", "loopback", "management", "spare"]
VLAN_ROLES = ["server"]

SITES = ["atl", "ord", "jfk", "den", "dfw", "iad", "bkk", "sfo", "iah", "mco"]

DEVICES = (
    ("edge1", "active", "7280R3", "profile1", "edge", ["red", "green"]),
    ("edge2", "active", "7280R3", "profile1", "edge", ["red", "blue", "green"]),
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

INTERFACE_MGMT_NAME = {"7280R3": "Management0"}

INTERFACE_L3_NAMES = {
    "7280R3": ["Ethernet1", "Ethernet2", "Ethernet3", "Ethernet4", "Ethernet5", "Ethernet6", "Ethernet7"],
}
INTERFACE_L2_NAMES = {
    "7280R3": ["Ethernet8"],
}


INTERFACE_ROLES_MAPPING = {
    "edge": ["peer", "peer", "backbone", "backbone", "transit", "transit", "peering", "spare"],
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
    ("pop-builder", "Script", ("operator",)),
    ("CRM Synchronization", "Script", ("operator",)),
    ("Jack Bauer", "User", ("operator",)),
    ("Chloe O'Brian", "User", ("operator",)),
    ("David Palmer", "User", ("operator",)),
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
    account_cloe = store.get("Chloe O'Brian")
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
                # circuit_id = next(EXTERNAL_CIRCUIT_IDS_GEN)
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


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    loopback_ip_dict: Dict[str, InfrahubNode] = {}

    for group in ACCOUNT_GROUPS:
        obj = await client.create(branch=branch, kind="Group", data={"name": group[0], "label": group[1]})
        await obj.save()
        store.set(key=group[0], node=obj)

        log.info(f"Group Created: {obj.name.value}")

    for account in ACCOUNTS:
        obj = await client.create(branch=branch, kind="Account", data={"name": account[0], "type": account[1]})
        await obj.save()
        store.set(key=account[0], node=obj)
        log.info(f"Account Created: {obj.name.value}")

    group_eng = store.get("network_engineering")
    group_ops = store.get("network_operation")
    account_pop = store.get("pop-builder")
    account_cloe = store.get("Chloe O'Brian")
    account_crm = store.get("CRM Synchronization")

    # ------------------------------------------
    # Create Organizations, BGP Peer Groups
    # ------------------------------------------
    for org in ORGANIZATIONS:
        obj = await client.create(
            branch=branch, kind="Organization", data={"name": {"value": org[0], "is_protected": True}}
        )
        await obj.save()

        asn = await client.create(
            branch=branch,
            kind="AutonomousSystem",
            data={
                "name": {"value": f"AS{org[1]}", "source": account_pop.id, "owner": account_cloe.id},
                "asn": {"value": org[1], "source": account_pop.id, "owner": account_cloe.id},
                "organization": {"id": obj.id, "source": account_pop.id},
            },
        )
        await asn.save()

        store.set(key=org[0], node=asn)
        store.set(key=org[0], node=obj)
        log.info(f"Organization Created: {obj.name.value} | {asn.asn.value}")

    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        remote_as = store.get(kind="AutonomousSystem", key=peer_group[4], default=None)
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
        await obj.save()

        store.set(key=peer_group[0], node=obj)
        log.info(f"Peer Group Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & Tags
    # ------------------------------------------
    log.info("Creating Roles, Status & Tag")
    for role in DEVICE_ROLES + INTF_ROLES + VLAN_ROLES:
        obj = await client.create(branch=branch, kind="Role", name={"value": role, "source": account_pop.id})
        await obj.save()
        store.set(key=role, node=obj)
        log.info(f" Created Role: {role}")

    for status in STATUSES:
        obj = await client.create(branch=branch, kind="Status", name={"value": status, "source": account_pop.id})
        await obj.save()
        store.set(key=status, node=obj)
        log.info(f" Created Status: {status}")

    for tag in TAGS:
        obj = await client.create(branch=branch, kind="Tag", name={"value": tag, "source": account_pop.id})
        await obj.save()
        store.set(key=tag, node=obj)
        log.info(f" Created Tag: {tag}")

    active_status = store.get(kind="Status", key="active")
    internal_as = store.get(kind="AutonomousSystem", key="Duff")

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site & Device")

    SITE_NAMES = site_names_generator(nbr_site=5)

    for site_idx, site_name in enumerate(SITE_NAMES):
        await generate_site(site_name=site_name, client=client, branch=branch, log=log)

    # --------------------------------------------------
    # CREATE Full Mesh iBGP SESSION between all the Edge devices
    # --------------------------------------------------
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
                    await obj.save()

                    log.info(
                        f" Created BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
                    )

    # # --------------------------------------------------
    # # CREATE BACKBONE LINKS & CIRCUITS
    # # --------------------------------------------------
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
