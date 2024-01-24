import copy
from collections import defaultdict
from ipaddress import IPv4Network

from infrahub_sdk import UUIDT

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

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

STATUSES = ["active", "provisioning", "maintenance", "drained"]

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

INTERFACE_OBJS = defaultdict(list)

ACCOUNTS = (
    ("pop-builder", "Script", ("operator",)),
    # ("nelly", "User", ("network-engineer", "operator")),
    # ("mary", "User", ("manager",)),
)

BGP_PEER_GROUPS = (
    ("POP_INTERNAL", "IMPORT_INTRA_POP", "EXPORT_INTRA_POP", "Duff", "Duff"),
    ("POP_GLOBAL", "IMPORT_POP_GLOBAL", "EXPORT_POP_GLOBLA", "Duff", None),
    ("TRANSIT_DEFAULT", "IMPORT_TRANSIT", "EXPORT_PUBLIC_PREFIX", "Duff", None),
    ("TRANSIT_TELIA", "IMPORT_TRANSIT", "EXPORT_PUBLIC_PREFIX", "Duff", "Telia"),
    ("IX_DEFAULT", "IMPORT_IX", "EXPORT_PUBLIC_PREFIX", "Duff", None),
)


log = get_logger()


async def load_data(db: InfrahubDatabase):
    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    accounts_dict = {}
    tags_dict = {}
    orgs_dict = {}
    asn_dict = {}

    peer_group_dict = {}

    loopback_ip_dict = {}
    device_dict = {}

    for account in ACCOUNTS:
        obj = await Node.init(db=db, schema="Account")
        await obj.new(db=db, name=account[0], type=account[1])
        await obj.save(db=db)
        accounts_dict[account[0]] = obj

        # for group in account[2]:
        #     groups_dict[group].add_account(obj)

        log.info(f"Account Created: {obj.name.value}")

    for org in ORGANIZATIONS:
        obj = await Node.init(db=db, schema="Organization")
        await obj.new(db=db, name=org[0])
        await obj.save(db=db)

        asn = await Node.init(db=db, schema="AutonomousSystem")
        await asn.new(db=db, name=f"AS{org[1]}", asn=org[1], organization=obj)
        await asn.save(db=db)

        asn_dict[org[0]] = asn
        orgs_dict[org[0]] = obj
        log.info(f"Organization Created: {obj.name.value} | {asn.asn.value}")

    for peer_group in BGP_PEER_GROUPS:
        obj = await Node.init(db=db, schema="BGPPeerGroup")
        await obj.new(
            db=db,
            name=peer_group[0],
            import_policies=peer_group[1],
            export_policies=peer_group[2],
            local_as=asn_dict.get(peer_group[3], None),
            remote_as=asn_dict.get(peer_group[4], None),
        )
        await obj.save(db=db)

        peer_group_dict[peer_group[0]] = obj
        log.info(f"Peer Group Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & DeviceProfile
    # ------------------------------------------
    for tag in TAGS:
        obj = await Node.init(db=db, schema="Tag")
        await obj.new(db=db, name=tag)
        await obj.save(db=db)
        tags_dict[tag] = obj
        log.info(f" Created Tag: {tag}")

    active_status = "active"
    internal_as = asn_dict["Duff"]

    log.info("Creating Site & Device")

    for site_idx, site_name in enumerate(SITES):
        site = await Node.init(db=db, schema="Location")
        await site.new(db=db, name=site_name, type="SITE")
        await site.save(db=db)
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
            device_type = device[2]

            obj = await Node.init(db=db, schema="Device")
            await obj.new(
                db=db,
                site=site,
                name=device_name,
                status=device[1],
                type=device[2],
                role=device[4],
                # source=pop_builder_account,
                asn=asn_dict["Duff"],
                tags=[tags_dict[tag_name] for tag_name in device[5]],
            )
            await obj.save(db=db)

            device_dict[device_name] = obj
            log.info(f"- Created Device: {device_name}")

            # Loopback Interface
            intf = await Node.init(db=db, schema="Interface")
            await intf.new(
                db=db,
                device=obj.id,
                name="Loopback0",
                enabled=True,
                status=active_status,
                role="loopback",
                speed=1000,
                # source=pop_builder_account,
            )
            await intf.save(db=db)

            ip = await Node.init(db=db, schema="IPAddress")
            await ip.new(db=db, interface=intf.id, address=f"{str(next(LOOPBACK_POOL))}/32")
            await ip.save(db=db)

            loopback_ip_dict[device_name] = ip

            # Management Interface
            intf = await Node.init(db=db, schema="Interface")
            await intf.new(
                db=db,
                device=obj.id,
                name=INTERFACE_MGMT_NAME[device_type],
                enabled=True,
                status=active_status,
                role="management",
                speed=1000,
                # source=pop_builder_account,
            )
            await intf.save(db=db)

            ip = await Node.init(db=db, schema="IPAddress")
            await ip.new(db=db, interface=intf.id, address=f"{str(next(MANAGEMENT_IPS))}/24")
            await ip.save(db=db)

            # Other Interfaces
            for intf_idx, intf_name in enumerate(INTERFACE_NAMES[device_type]):
                intf_role = INTERFACE_ROLES_MAPPING[device[4]][intf_idx]

                intf = await Node.init(db=db, schema="Interface")
                await intf.new(
                    db=db,
                    device=obj.id,
                    name=intf_name,
                    speed=10000,
                    enabled=True,
                    status=active_status,
                    role=intf_role,
                    # source=pop_builder_account,
                )
                await intf.save(db=db)

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

                ip = await Node.init(db=db, schema="IPAddress")
                await ip.new(
                    db=db,
                    interface=intf.id,
                    address=address,
                    # source=pop_builder_account
                )
                await ip.save(db=db)

                # Create Circuit and BGP session for transit and peering
                if intf_role in ["transit", "peering"]:
                    circuit_id = next(EXTERNAL_CIRCUIT_IDS_GEN)
                    transit_providers = ["Telia", "Colt"]

                    if intf_role == "transit":
                        provider_name = transit_providers[intf_idx % 2]
                    elif intf_role == "peering":
                        provider_name = "Equinix"

                    provider = orgs_dict[provider_name]

                    circuit = await Node.init(db=db, schema="Circuit")
                    await circuit.new(
                        db=db,
                        circuit_id=circuit_id,
                        vendor_id=f"{provider_name.upper()}-{UUIDT().short()}",
                        provider=provider.id,
                        # type=intf_role.upper(),
                        status=active_status,
                        role=intf_role,
                    )
                    await circuit.save(db=db)

                    endpoint1 = await Node.init(db=db, schema="CircuitEndpoint")
                    await endpoint1.new(db=db, site=site, circuit=circuit.id, connected_interface=intf.id)
                    await endpoint1.save(db=db)

                    intf.description.value = f"Connected to {provider_name} via {circuit_id}"

                    if intf_role == "transit":
                        peer_group_name = (
                            "TRANSIT_TELIA" if "telia" in provider.name.value.lower() else "TRANSIT_DEFAULT"
                        )

                        peer_ip = await Node.init(db=db, schema="IPAddress")
                        await peer_ip.new(
                            db=db,
                            address=peer_address,
                            # source=pop_builder_account
                        )
                        await peer_ip.save(db=db)

                        peer_as = asn_dict[provider_name]
                        bgp_session = await Node.init(db=db, schema="BGPSession")
                        await bgp_session.new(
                            db=db,
                            type="EXTERNAL",
                            local_as=internal_as,
                            local_ip=ip,
                            remote_as=peer_as,
                            remote_ip=peer_ip,
                            peer_group=peer_group_dict[peer_group_name],
                            device=device_dict[device_name],
                            status=active_status,
                            role=intf_role,
                        )
                        await bgp_session.save(db=db)

                        log.info(
                            f" Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                        )

        # Connect pair within a site together
        for idx in range(0, 2):
            intf1 = INTERFACE_OBJS[f"{site_name}-edge1"][idx]
            intf2 = INTERFACE_OBJS[f"{site_name}-edge2"][idx]

            await intf1.connected_interface.update(db=db, data=intf2)
            intf1.description.value = f"Connected to {site_name}-edge2 {intf2.name.value}"
            await intf1.save(db=db)

            intf2.description.value = f"Connected to {site_name}-edge1 {intf1.name.value}"
            await intf2.save(db=db)

            log.debug(f"Connected  '{site_name}-edge1::{intf1.name.value}' <> '{site_name}-edge2::{intf2.name.value}'")

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

            obj = await Node.init(db=db, schema="BGPSession")
            await obj.new(
                db=db,
                type="INTERNAL",
                local_as=internal_as,
                local_ip=loopback1,
                remote_as=internal_as,
                remote_ip=loopback2,
                peer_group=peer_group_dict[peer_group_name].id,
                device=device_dict[device1].id,
                status=active_status,
                role="backbone",
            )
            await obj.save(db=db)

            log.info(
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
        obj = await Node.init(db=db, schema="Circuit")
        await obj.new(
            db=db,
            circuit_id=BACKBONE_CIRCUIT_IDS[idx],
            vendor_id=f"{provider_name.upper()}-{UUIDT().short()}",
            provider=provider,
            # type="DARK FIBER",
            status=active_status,
            role="backbone",
        )
        await obj.save(db=db)

        endpoint1 = await Node.init(db=db, schema="CircuitEndpoint")
        await endpoint1.new(db=db, site=site1, circuit=obj, connected_interface=intf1)
        await endpoint1.save(db=db)
        endpoint2 = await Node.init(db=db, schema="CircuitEndpoint")
        await endpoint2.new(db=db, site=site2, circuit=obj, connected_interface=intf2)
        await endpoint2.save(db=db)

        intf11 = await NodeManager.get_one(db=db, id=intf1.id)
        intf11.description.value = f"Connected to {site2}-{device} via {circuit_id}"
        await intf11.save(db=db)

        intf21 = await NodeManager.get_one(db=db, id=intf2.id)
        intf21.description.value = f"Connected to {site1}-{device} via {circuit_id}"
        await intf21.save(db=db)

        log.info(f"Connected  '{site1}-{device}::{intf1.name.value}' <> '{site2}-{device}::{intf2.name.value}'")
