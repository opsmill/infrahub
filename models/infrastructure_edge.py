import copy
import logging
import uuid
from asyncio import run as aiorun
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Dict, List

import typer
from rich.logging import RichHandler

from infrahub_client import InfrahubClient, InfrahubNode

# flake8: noqa
# pylint: skip-file

DEVICE_ROLES = ["edge"]
INTF_ROLES = ["backbone", "transit", "peering", "peer", "loopback", "management", "spare"]
SITES = ["atl1", "ord1", "jfk1"]

DEVICES = (
    ("edge1", "active", "7280R3", "profile1", "edge", ["red", "green"]),
    ("edge2", "active", "7280R3", "profile1", "edge", ["red", "blue", "green"]),
)

NETWORKS_POOL_INTERNAL = IPv4Network("10.0.0.0/8").subnets(new_prefix=16)
LOOPBACK_POOL = next(NETWORKS_POOL_INTERNAL).hosts()
P2P_NETWORK_POOL = next(NETWORKS_POOL_INTERNAL).subnets(new_prefix=31)
NETWORKS_POOL_EXTERNAL = IPv4Network("203.0.113.0/24").subnets(new_prefix=29)

MANAGEMENT_IPS = IPv4Network("172.20.20.16/28").hosts()

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
EXTERNAL_CIRCUIT_IDS = [
    "DUFF-2245961",
    "DUFF-7192793",
    "DUFF-3144589",
    "DUFF-5095131",
    "DUFF-2825046",
    "DUFF-2131922",
    "DUFF-5943071",
    "DUFF-2939471",
    "DUFF-2322077",
    "DUFF-5282855",
    "DUFF-1071473",
    "DUFF-4412567",
    "DUFF-2359629",
    "DUFF-5535692",
    "DUFF-8417288",
    "DUFF-1532538",
    "DUFF-4906231",
    "DUFF-3422501",
    "DUFF-5874882",
    "DUFF-2067921",
    "DUFF-4849865",
    "DUFF-9705052",
    "DUFF-5388108",
    "DUFF-1906923",
    "DUFF-1989915",
    "DUFF-8338698",
]

EXTERNAL_CIRCUIT_IDS_GEN = (cid for cid in EXTERNAL_CIRCUIT_IDS)


INTERFACE_MGMT_NAME = {"7280R3": "Management0"}

INTERFACE_NAMES = {
    "7280R3": ["Ethernet1", "Ethernet2", "Ethernet3", "Ethernet4", "Ethernet5", "Ethernet6", "Ethernet7", "Ethernet8"],
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


LOGGER = logging.getLogger("infrahub")


def load_data():
    aiorun(_load_data())


async def _load_data():
    FORMAT = "%(message)s"
    logging.basicConfig(level="DEBUG", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger()
    client = await InfrahubClient.init(insert_tracker=True)

    await run(client=client, log=log)


async def run(client: InfrahubClient, log: logging.Logger):
    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    accounts_dict: Dict[str, InfrahubNode] = {}
    groups_dict: Dict[str, InfrahubNode] = {}
    tags_dict: Dict[str, InfrahubNode] = {}
    orgs_dict: Dict[str, InfrahubNode] = {}
    asn_dict: Dict[str, InfrahubNode] = {}
    peer_group_dict: Dict[str, InfrahubNode] = {}
    loopback_ip_dict: Dict[str, InfrahubNode] = {}
    device_dict: Dict[str, InfrahubNode] = {}
    statuses_dict: Dict[str, InfrahubNode] = {}
    roles_dict: Dict[str, InfrahubNode] = {}

    for group in ACCOUNT_GROUPS:
        obj = await client.create(kind="Group", data={"name": group[0], "label": group[1]})
        await obj.save()
        groups_dict[group[0]] = obj

        log.info(f"Group Created: {obj.name.value}")

    for account in ACCOUNTS:
        obj = await client.create(kind="Account", data={"name": account[0], "type": account[1]})
        await obj.save()
        accounts_dict[account[0]] = obj

        log.info(f"Account Created: {obj.name.value}")

    group_eng = groups_dict["network_engineering"]
    group_ops = groups_dict["network_operation"]
    account_pop = accounts_dict["pop-builder"]
    account_cloe = accounts_dict["Chloe O'Brian"]
    account_crm = accounts_dict["CRM Synchronization"]

    for org in ORGANIZATIONS:
        obj = await client.create(kind="Organization", data={"name": {"value": org[0], "is_protected": True}})
        await obj.save()

        asn = await client.create(
            kind="AutonomousSystem",
            data={
                "name": {"value": f"AS{org[1]}", "source": account_pop.id, "owner": account_cloe.id},
                "asn": {"value": org[1], "source": account_pop.id, "owner": account_cloe.id},
                "organization": {"id": obj.id, "source": account_pop.id},
            },
        )
        await asn.save()

        asn_dict[org[0]] = asn
        orgs_dict[org[0]] = obj
        log.info(f"Organization Created: {obj.name.value} | {asn.asn.value}")

    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        remote_as = asn_dict.get(peer_group[4])
        if remote_as:
            remote_as_id = remote_as.id

        obj = await client.create(
            kind="BGPPeerGroup",
            name={"value": peer_group[0], "source": account_pop.id},
            import_policies={"value": peer_group[1], "source": account_pop.id},
            export_policies={"value": peer_group[2], "source": account_pop.id},
            local_as=asn_dict.get(peer_group[3]).id,
            remote_as=remote_as_id,
        )
        await obj.save()

        peer_group_dict[peer_group[0]] = obj
        log.info(f"Peer Group Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & DeviceProfile
    # ------------------------------------------

    log.info("Creating Roles, Status & Tag")
    for role in DEVICE_ROLES + INTF_ROLES:
        obj = await client.create(kind="Role", name={"value": role, "source": account_pop.id})
        await obj.save()
        roles_dict[role] = obj
        log.info(f" Created Role: {role}")

    for status in STATUSES:
        obj = await client.create(kind="Status", name={"value": status, "source": account_pop.id})
        await obj.save()
        statuses_dict[status] = obj
        log.info(f" Created Status: {status}")

    for tag in TAGS:
        obj = await client.create(kind="Tag", name={"value": tag, "source": account_pop.id})
        await obj.save()
        tags_dict[tag] = obj
        log.info(f" Created Tag: {tag}")

    active_status = statuses_dict["active"]
    internal_as = asn_dict["Duff"]

    log.info("Creating Site & Device")

    # { "value": role, "source": account_pop.id },
    for site_idx, site_name in enumerate(SITES):
        site = await client.create(
            kind="Location",
            name={"value": site_name, "is_protected": True, "source": account_crm.id},
            type={"value": "SITE", "is_protected": True, "source": account_crm.id},
        )
        await site.save()
        log.info(f"Created Site: {site_name}")

        # site_networks = next(NETWORKS_POOL_INTERNAL).subnets(new_prefix=24)
        peer_networks = {
            0: next(P2P_NETWORK_POOL).hosts(),
            1: next(P2P_NETWORK_POOL).hosts(),
        }

        # Build a new list with the names of the other sites for later
        other_sites = copy.copy(SITES)
        other_sites.remove(site_name)
        other_sites = sorted(other_sites)

        for idx, device in enumerate(DEVICES):
            device_name = f"{site_name}-{device[0]}"
            status_id = statuses_dict[device[1]].id
            role_id = roles_dict[device[4]].id
            device_type = device[2]

            obj = await client.create(
                kind="Device",
                site={"id": site.id, "source": account_pop.id, "is_protected": True},
                name={"value": device_name, "source": account_pop.id, "is_protected": True},
                status={"id": status_id, "owner": group_ops.id},
                type={"value": device[2], "source": account_pop.id},
                role={"id": role_id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
                asn={"id": asn_dict["Duff"].id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
                tags=[tags_dict[tag_name].id for tag_name in device[5]],
            )
            await obj.save()

            device_dict[device_name] = obj
            log.info(f"- Created Device: {device_name}")

            # Loopback Interface
            intf = await client.create(
                kind="Interface",
                device={"id": obj.id, "is_protected": True},
                name={"value": "Loopback0", "source": account_pop.id, "is_protected": True},
                enabled=True,
                status={"id": active_status.id, "owner": group_ops.id},
                role={"id": roles_dict["loopback"].id, "source": account_pop.id, "is_protected": True},
                speed=1000,
                # source=pop_builder_account,
            )
            await intf.save()

            ip = await client.create(
                kind="IPAddress",
                interface={"id": intf.id, "source": account_pop.id},
                address={"value": f"{str(next(LOOPBACK_POOL))}/32", "source": account_pop.id},
            )
            await ip.save()

            loopback_ip_dict[device_name] = ip

            # Management Interface
            intf = await client.create(
                kind="Interface",
                device={"id": obj.id, "is_protected": True},
                name={"value": INTERFACE_MGMT_NAME[device_type], "source": account_pop.id},
                enabled={"value": True, "owner": group_eng.id},
                status={"id": active_status.id, "owner": group_eng.id},
                role={"id": roles_dict["management"].id, "source": account_pop.id, "is_protected": True},
                speed=1000,
            )
            await intf.save()

            ip = await client.create(kind="IPAddress", interface=intf.id, address=f"{str(next(MANAGEMENT_IPS))}/24")
            await ip.save()

            # Other Interfaces
            for intf_idx, intf_name in enumerate(INTERFACE_NAMES[device_type]):
                intf_role = INTERFACE_ROLES_MAPPING[device[4]][intf_idx]
                intf_role_id = roles_dict[intf_role].id

                intf = await client.create(
                    kind="Interface",
                    device={"id": obj.id, "is_protected": True},
                    name=intf_name,
                    speed=10000,
                    enabled=True,
                    status={"id": active_status.id, "owner": group_ops.id},
                    role={"id": intf_role_id, "source": account_pop.id},
                )
                await intf.save()

                INTERFACE_OBJS[device_name].append(intf)

                address = None
                if intf_role == "peer":
                    address = f"{str(next(peer_networks[intf_idx]))}/31"

                if intf_role == "backbone":
                    site_idx = intf_idx - 2
                    other_site_name = other_sites[site_idx]  # f"{other_sites[site_idx]}-{device[0]}"
                    sites = sorted([site_name, other_site_name])
                    link_id = (sites[0], device[0], sites[1], device[0])
                    address = f"{str(next(P2P_NETWORKS_POOL[link_id]))}/31"

                if intf_role in ["transit", "peering"]:
                    subnet = next(NETWORKS_POOL_EXTERNAL).hosts()
                    address = f"{str(next(subnet))}/29"

                    peer_address = f"{str(next(subnet))}/29"

                if not address:
                    continue

                ip = await client.create(
                    kind="IPAddress",
                    interface={"id": intf.id, "source": account_pop.id},
                    address={"value": address, "source": account_pop.id},
                )
                await ip.save()

                # Create Circuit and BGP session for transit and peering
                if intf_role in ["transit", "peering"]:
                    circuit_id = next(EXTERNAL_CIRCUIT_IDS_GEN)
                    transit_providers = ["Telia", "Colt"]

                    if intf_role == "transit":
                        provider_name = transit_providers[intf_idx % 2]
                    elif intf_role == "peering":
                        provider_name = "Equinix"

                    provider = orgs_dict[provider_name]

                    circuit = await client.create(
                        kind="Circuit",
                        circuit_id=circuit_id,
                        vendor_id=f"{provider_name.upper()}-{str(uuid.uuid4())[:8]}",
                        provider=provider.id,
                        status={"id": active_status.id, "owner": group_ops.id},
                        role={"id": roles_dict[intf_role].id, "source": account_pop.id, "owner": group_eng.id},
                    )
                    await circuit.save()

                    endpoint1 = await client.create(
                        kind="CircuitEndpoint", site=site, circuit=circuit.id, connected_interface=intf.id
                    )
                    await endpoint1.save()

                    intf.description.value = f"Connected to {provider_name} via {circuit_id}"

                    if intf_role == "transit":
                        peer_group_name = (
                            "TRANSIT_TELIA" if "telia" in provider.name.value.lower() else "TRANSIT_DEFAULT"
                        )

                        peer_ip = await client.create(
                            kind="IPAddress",
                            address=peer_address,
                        )
                        await peer_ip.save()

                        peer_as = asn_dict[provider_name]
                        bgp_session = await client.create(
                            kind="BGPSession",
                            type="EXTERNAL",
                            local_as=internal_as.id,
                            local_ip=ip.id,
                            remote_as=peer_as.id,
                            remote_ip=peer_ip.id,
                            peer_group=peer_group_dict[peer_group_name].id,
                            device=device_dict[device_name].id,
                            status=active_status.id,
                            role=roles_dict[intf_role].id,
                        )
                        await bgp_session.save()

                        log.info(
                            f" Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                        )

        # Connect pair within a site together
        for idx in range(0, 2):
            intf1 = INTERFACE_OBJS[f"{site_name}-edge1"][idx]
            intf2 = INTERFACE_OBJS[f"{site_name}-edge2"][idx]

            # intf1.connected_interface.add(intf2)
            intf1.description.value = f"Connected to {site_name}-edge2 {intf2.name.value}"
            await intf1.save()

            intf2.description.value = f"Connected to {site_name}-edge1 {intf1.name.value}"
            await intf2.save()

            log.info(f"Connected  '{site_name}-edge1::{intf1.name.value}' <> '{site_name}-edge2::{intf2.name.value}'")

    # --------------------------------------------------
    # CREATE iBGP SESSION
    # --------------------------------------------------

    for device1, loopback1 in loopback_ip_dict.items():
        for device2, loopback2 in loopback_ip_dict.items():
            if device1 == device2:
                continue
            site1 = device1.split("-")[0]
            site2 = device2.split("-")[0]

            peer_group_name = "POP_INTERNAL" if site1 == site2 else "POP_GLOBAL"

            obj = await client.create(
                kind="BGPSession",
                type="INTERNAL",
                local_as=internal_as.id,
                local_ip=loopback1.id,
                remote_as=internal_as.id,
                remote_ip=loopback2.id,
                peer_group=peer_group_dict[peer_group_name].id,
                device=device_dict[device1].id,
                status=active_status.id,
                role=roles_dict["backbone"].id,
            )
            await obj.save()

            LOGGER.info(
                f" Created BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
            )

    # --------------------------------------------------
    # CREATE BACKBONE LINKS & CIRCUITS
    # --------------------------------------------------
    for idx, backbone_link in enumerate(P2P_NETWORKS_POOL.keys()):
        site1 = backbone_link[0]
        site2 = backbone_link[2]
        device = backbone_link[1]

        # Build a new list with the names of the other sites for later
        other_site_site1 = copy.copy(SITES)
        other_site_site1.remove(site1)
        other_site_site1 = sorted(other_site_site1)

        other_site_site2 = copy.copy(SITES)
        other_site_site2.remove(site2)
        other_site_site2 = sorted(other_site_site2)

        intf1 = INTERFACE_OBJS[f"{site1}-{device}"][other_site_site1.index(site2) + 2]
        intf2 = INTERFACE_OBJS[f"{site2}-{device}"][other_site_site2.index(site1) + 2]

        circuit_id = BACKBONE_CIRCUIT_IDS[idx]

        if idx <= 2:
            provider_name = "Lumen"
        else:
            provider_name = "Zayo"

        provider = orgs_dict[provider_name]
        obj = await client.create(
            kind="Circuit",
            circuit_id=BACKBONE_CIRCUIT_IDS[idx],
            vendor_id=f"{provider_name.upper()}-{str(uuid.uuid4())[:8]}",
            provider=provider,
            # type="DARK FIBER",
            status=active_status,
            role=roles_dict["backbone"],
        )
        await obj.save()

        endpoint1 = await client.create(kind="CircuitEndpoint", site=site1, circuit=obj, connected_interface=intf1)
        await endpoint1.save()
        endpoint2 = await client.create(kind="CircuitEndpoint", site=site2, circuit=obj, connected_interface=intf2)
        await endpoint2.save()

        intf11 = await client.get(kind="Interface", id=intf1.id)

        intf11.description.value = f"Connected to {site2}-{device} via {circuit_id}"
        await intf11.save()

        intf21 = await client.get(kind="Interface", id=intf2.id)
        intf21.description.value = f"Connected to {site1}-{device} via {circuit_id}"
        await intf21.save()

        LOGGER.info(f"Connected  '{site1}-{device}::{intf1.name.value}' <> '{site2}-{device}::{intf2.name.value}'")


if __name__ == "__main__":
    typer.run(load_data)
