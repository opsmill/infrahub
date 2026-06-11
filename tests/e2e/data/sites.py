"""Sites slice: the five sites with their VLANs, devices, interfaces, IPs, circuits and BGP sessions.

Faithful transcription of ``models/infrastructure_edge.py``:

* data tables ``SITES`` (lines 402-413), ``DEVICE_PATTERNS`` (lines 453-481),
  the per-type interface name tables of the ``Device`` model (lines 204-244),
  ``INTERFACE_MGMT_NAME`` / ``LAG_INTERFACE_L2`` / ``INTERFACE_L3_ROLES_MAPPING``
  / ``INTERFACE_L2_ROLES_MAPPING`` / ``LAG_INTERFACE_L2_ROLES_MAPPING`` /
  ``INTERFACE_L2_MODE_MAPPING`` / ``MLAG_DOMAINS`` / ``MLAG_INTERFACE_L2``
  (lines 602-675) and ``VLANS`` (lines 842-845),
* ``site_generator`` (lines 571-599) at the medium profile (``num_sites=5`` ->
  atl1/Atlanta, ord1/Chicago, jfk1/New York, den1/Denver, dfw1/Dallas, all in
  United States of America) and ``SiteDesign`` (lines 486-554) at
  ``num_device_per_site=6`` (the special case: 2 edge + 2 core + 2 leaf,
  generated in pattern order edge1, edge2, core1, core2, leaf1, leaf2),
* ``generate_site_vlans`` (lines 1293-1329), ``generate_site_mlag_domain``
  (lines 1332-1381), ``find_and_connect_interfaces`` (lines 848-877, the
  current version that persists BOTH sides of the symmetric
  ``connected_endpoint``) and ``generate_site`` (lines 1384-1879), sequenced
  site by site exactly like ``run()`` (lines 2772-2794) so every pool
  allocation (loopbacks, management addresses, peer-link /31s,
  upstream/peering /29s) happens in the script's order — tests assert the
  resulting next-free values (172.16.0.31/16 management, 10.0.0.<n>/32
  loopback of device #n).

Preserved script quirks (NOT deviations):

* the peer-link /31 ``hosts()`` generators are rebuilt per edge device, so
  edge1 and edge2 compute the SAME host addresses and the second, upserted
  save re-points the shared ``IpamIPAddress`` at edge2 (net effect: 2
  peer-link addresses per site) — see ``_allocate_peer_networks``,
* the ``peering`` branch of ``generate_site`` never reassigns the
  ``provider`` variable, so the peering circuit keeps the Colt provider node
  from the preceding upstream interface while its ``vendor_id`` uses the
  EQUINIX- prefix — the atl1-delete-upstream scenario depends on matching 4
  Colt circuits per site.

Deviations:

* circuit ids: the script derives them from the PYTHONHASHSEED-salted
  ``hash()`` builtin (line 1611: ``str(uuid.UUID(int=abs(hash(seed))))[24:]``,
  12 hex chars), unstable across runs. Replaced by a deterministic md5 digest
  of the SAME seed string with the same final format so reruns produce
  identical ids; vendor ids keep the script's non-deterministic
  ``infrahub_sdk.uuidt.UUIDT().short()``.
* async SDK with kind STRINGS instead of generated protocol classes; the
  script's ``client.store`` keys and ``INTERFACE_OBJS`` module global become
  module-local dicts and the returned ``SitesHandle``.
* ``branch="main"`` is passed explicitly where the script relied on the
  client's default branch (the MLAG domain/interface creates of
  ``generate_site_mlag_domain``).
* the script's ``cable_batch`` (created and executed but never filled, lines
  1542/1700) is not transcribed; log-only code is dropped.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.uuidt import UUIDT

from data.handles import SitesHandle

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.batch import InfrahubBatch
    from infrahub_sdk.node import InfrahubNode

    from data.handles import IpamPoolsHandle, LocationsHandle, OrgRegistryHandle, RbacHandle

BRANCH = "main"

# (lines 567-568)
ACTIVE_STATUS = "active"

# PROFILES["medium"] (line 53): 5 sites, 6 devices per site.
NUM_SITES = 5

# name / country / city / contact, cycled by _site_generator (lines 402-413)
SITES = (
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
)

# name / status / type / role / tags / platform per pattern (lines 453-481).
# The script's Device model also carries profile="profile1", never read by generate_site — dropped.
DEVICE_PATTERNS = {
    "LEAF": {
        "name": "leaf",
        "status": "active",
        "type": "7010TX-48",
        "role": "leaf",
        "tags": ["red", "green"],
        "platform": "Cisco IOS",
    },
    "CORE": {
        "name": "core",
        "status": "active",
        "type": "MX204",
        "role": "core",
        "tags": ["blue"],
        "platform": "Juniper JunOS",
    },
    "EDGE": {
        "name": "edge",
        "status": "active",
        "type": "7280R3",
        "role": "edge",
        "tags": ["red", "green"],
        "platform": "Arista EOS",
    },
}

# SiteDesign (lines 486-554): num_device_per_site=6 is the hardcoded special case -> 2/2/2,
# implemented (lines 542-551) in pattern order EDGE, CORE, LEAF.
NUM_EDGE_DEVICE = 2
NUM_CORE_DEVICE = 2
NUM_LEAF_DEVICE = 2

# Device.l3_interface_names (lines 215-244)
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

# Device.l2_interface_names (lines 204-212)
INTERFACE_L2_NAMES = {
    "7280R3": ["Ethernet11", "Ethernet12"],
    "ASR1002-HX": ["Ethernet11", "Ethernet12"],
    "MX204": ["et-0/0/3"],
    "7010TX-48": [f"Ethernet{idx}" for idx in range(1, 49)],
}

# (lines 602-607)
INTERFACE_MGMT_NAME = {
    "7280R3": "Management0",
    "7010TX-48": "Management0",
    "ASR1002-HX": "Management0",
    "MX204": "MGMT",
}

# (lines 610-626)
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

# (lines 628-650)
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

# (lines 652-657)
INTERFACE_L2_ROLES_MAPPING = {
    "leaf": [
        "peer",
        "peer",
    ],
}

# (lines 659-661)
LAG_INTERFACE_L2_ROLES_MAPPING: dict[str, dict[str, str]] = {
    "leaf": {"port-channel1": "peer", "port-channel2": "server"}
}

# (line 663)
INTERFACE_L2_MODE_MAPPING = {"peer": "Trunk (ALL)"}

# (line 665)
MLAG_DOMAINS = {"leaf": {"domain_id": 1, "peer_interfaces": ["port-channel1", "port-channel1"]}}

# (lines 667-675)
MLAG_INTERFACE_L2 = {
    "leaf": [
        {
            "mlag_id": 2,
            "mlag_domain": 1,
            "members": ["port-channel2", "port-channel2"],
        }
    ]
}

# vlan_id / role (lines 842-845)
VLANS = (
    {"id": 200, "role": "server"},
    {"id": 400, "role": "management"},
)

# generate_site local (line 1613): index parity of the upstream interface picks the provider.
UPSTREAM_PROVIDERS = ["Arelion", "Colt Technology Services"]


def _site_generator(nbr_site: int) -> list[dict[str, str]]:
    """Transcribes ``site_generator`` (lines 571-599): cycle SITES, suffixing the loop index."""
    sites: list[dict[str, str]] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        sites.extend([{**site, "name": f"{site['name']}{idx}"} for site in SITES[:nbr_this_loop]])

    return sites


def _site_devices() -> list[dict[str, Any]]:
    """Transcribes ``SiteDesign.implement``/``device_generator`` (lines 524-551) for the 2/2/2 design."""
    devices: list[dict[str, Any]] = []
    for pattern_name, number in (("EDGE", NUM_EDGE_DEVICE), ("CORE", NUM_CORE_DEVICE), ("LEAF", NUM_LEAF_DEVICE)):
        pattern = DEVICE_PATTERNS[pattern_name]
        devices.extend({**pattern, "name": f"{pattern['name']}{i}", "idx": i} for i in range(1, number + 1))
    return devices


def _deterministic_circuit_id_unique(seed: str) -> str:
    """DEVIATION (see module docstring): deterministic stand-in for the script's salted hash.

    Script line 1611: ``str(uuid.UUID(int=abs(hash(seed))))[24:]`` — the last 12 hex chars
    of a UUID built from the seed's ``hash()``. Same construction and format, with the
    PYTHONHASHSEED-dependent ``abs(hash(seed))`` replaced by the seed's 128-bit md5 digest.
    """
    digest = int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16)
    return str(uuid.UUID(int=digest))[24:]


@dataclass
class _SiteContext:
    """Cross-site nodes and metadata ids generate_site read from ``client.store``."""

    client: InfrahubClient
    account_pop_id: str
    account_crm_id: str
    group_eng_id: str
    group_ops_id: str
    internal_as_id: str
    asns: dict[str, str]
    peer_groups: dict[str, str]
    organizations: dict[str, str]
    tags: dict[str, str]
    platforms: dict[str, str]
    countries: dict[str, str]
    interconnection_pool: InfrahubNode
    loopback_pool: InfrahubNode
    management_pool: InfrahubNode
    external_pool: InfrahubNode


@dataclass
class _SiteState:
    """Per-site working state (the script's ``client.store`` keys for one site)."""

    site_name: str
    site_obj: InfrahubNode
    vlans: dict[str, InfrahubNode] = field(default_factory=dict)
    peer_network_hosts: dict[int, dict[int, Iterator[Any]]] = field(default_factory=dict)
    device_nodes: dict[str, InfrahubNode] = field(default_factory=dict)
    l3_interfaces: dict[str, InfrahubNode] = field(default_factory=dict)  # "<device>-l3-<idx>"
    l2_interfaces: dict[str, InfrahubNode] = field(default_factory=dict)  # "<device>-l2-<name>"
    lag_interfaces: dict[str, InfrahubNode] = field(default_factory=dict)  # "<device>-lagl2-<name>"
    mlag_domains: dict[str, InfrahubNode] = field(default_factory=dict)
    loopback_ips: dict[str, str] = field(default_factory=dict)  # device name -> address VALUE
    # The script's INTERFACE_OBJS: NODE OBJECTS, not ids — at append time the
    # interface is still unsaved (its id is assigned by the batched save).
    backbone_interfaces: dict[str, list[InfrahubNode]] = field(default_factory=dict)


async def _generate_site_vlans(ctx: _SiteContext, state: _SiteState) -> None:
    """Transcribes ``generate_site_vlans`` (lines 1293-1329)."""
    vlan_batch = await ctx.client.create_batch()
    for vlan in VLANS:
        vlan_name = f"{state.site_name}_{vlan['role']}"
        obj = await ctx.client.create(
            branch=BRANCH,
            kind="InfraVLAN",
            site={"id": state.site_obj.id, "source": ctx.account_pop_id, "is_protected": True},
            name={"value": vlan_name, "is_protected": True, "source": ctx.account_pop_id},
            vlan_id={
                "value": vlan["id"],
                "is_protected": True,
                "owner": ctx.group_eng_id,
                "source": ctx.account_pop_id,
            },
            status={"value": ACTIVE_STATUS, "owner": ctx.group_ops_id},
            role={"value": vlan["role"], "source": ctx.account_pop_id, "is_protected": True, "owner": ctx.group_eng_id},
        )
        vlan_batch.add(task=obj.save, node=obj)
        state.vlans[vlan_name] = obj

    async for _ in vlan_batch.execute():
        pass


async def _allocate_peer_networks(ctx: _SiteContext, state: _SiteState) -> None:
    """Transcribes the peer-link prefix allocation of ``generate_site`` (lines 1425-1447)."""
    # Here we need as much prefix as we have edge device
    peer_networks: list[InfrahubNode] = [
        await ctx.client.allocate_next_ip_prefix(
            resource_pool=ctx.interconnection_pool,
            kind="IpamIPPrefix",  # type: ignore[call-overload]
            branch=BRANCH,
        )
        for _ in range(NUM_EDGE_DEVICE)
    ]

    # QUIRK (preserved verbatim from lines 1439-1447): both edge devices of a pair get FRESH
    # hosts() generators over the SAME two /31 prefixes, so edge1 and edge2 compute identical
    # host addresses. With allow_upsert + the address uniqueness, the second save UPDATES the
    # node the first created — net effect: 2 peer-link IpamIPAddress per site, each ending up
    # pointed at the edge2 interface.
    for i in range(1, NUM_EDGE_DEVICE, 2):
        state.peer_network_hosts[i] = {
            0: peer_networks[i - 1].prefix.value.hosts(),
            1: peer_networks[i].prefix.value.hosts(),
        }
        state.peer_network_hosts[i + 1] = {
            0: peer_networks[i - 1].prefix.value.hosts(),
            1: peer_networks[i].prefix.value.hosts(),
        }


async def _create_devices(ctx: _SiteContext, state: _SiteState, devices: list[dict[str, Any]]) -> None:
    """Transcribes the device creation batch of ``generate_site`` (lines 1456-1489)."""
    device_batch = await ctx.client.create_batch()
    for device in devices:
        device_name = f"{state.site_name}-{device['name']}"
        platform_id = ctx.platforms[device["platform"]]

        obj = await ctx.client.create(
            branch=BRANCH,
            kind="InfraDevice",
            site={"id": state.site_obj.id, "source": ctx.account_pop_id, "is_protected": True},
            name={"value": device_name, "source": ctx.account_pop_id, "is_protected": True},
            status={"value": device["status"], "owner": ctx.group_ops_id},
            type={"value": device["type"], "source": ctx.account_pop_id},
            role={
                "value": device["role"],
                "source": ctx.account_pop_id,
                "is_protected": True,
                "owner": ctx.group_eng_id,
            },
            asn={
                "id": ctx.internal_as_id,
                "source": ctx.account_pop_id,
                "is_protected": True,
                "owner": ctx.group_eng_id,
            },
            tags=[ctx.tags[tag_name] for tag_name in device["tags"]],
            platform={"id": platform_id, "source": ctx.account_pop_id, "is_protected": True},
        )
        device_batch.add(task=obj.save, node=obj)
        state.device_nodes[device_name] = obj

    async for _ in device_batch.execute():
        pass


async def _create_loopback_and_management(ctx: _SiteContext, state: _SiteState, device: dict[str, Any]) -> None:
    """Transcribes the Loopback0 + management-interface block of ``generate_site`` (lines 1499-1536)."""
    device_name = f"{state.site_name}-{device['name']}"
    obj = state.device_nodes[device_name]

    # Loopback Interface
    intf = await ctx.client.create(
        branch=BRANCH,
        kind="InfraInterfaceL3",
        device={"id": obj.id, "is_protected": True},
        name={"value": "Loopback0", "source": ctx.account_pop_id, "is_protected": True},
        enabled=True,
        status=ACTIVE_STATUS,
        role="loopback",
        speed=1000,
    )
    await intf.save()

    ip = await ctx.client.allocate_next_ip_address(
        resource_pool=ctx.loopback_pool, identifier=device_name, data={"interface": intf.id}, branch=BRANCH
    )
    state.loopback_ips[device_name] = str(ip.address.value)

    # Management Interface
    intf = await ctx.client.create(
        branch=BRANCH,
        kind="InfraInterfaceL3",
        device={"id": obj.id, "is_protected": True},
        name={"value": INTERFACE_MGMT_NAME[device["type"]], "source": ctx.account_pop_id},
        enabled={"value": True, "owner": ctx.group_eng_id},
        status={"value": ACTIVE_STATUS, "owner": ctx.group_eng_id},
        role={"value": "management", "source": ctx.account_pop_id, "is_protected": True},
        speed=1000,
    )
    await intf.save()
    management_ip = await ctx.client.allocate_next_ip_address(
        resource_pool=ctx.management_pool, identifier=device_name, data={"interface": intf.id}, branch=BRANCH
    )

    # set the IP address of the device to the management interface IP address
    obj.primary_address = management_ip  # type: ignore[assignment]
    await obj.save()


async def _create_l3_interfaces(ctx: _SiteContext, state: _SiteState, device: dict[str, Any]) -> None:  # noqa: PLR0912, PLR0914
    """Transcribes the L3 interface / IP / circuit / BGP-session loop of ``generate_site`` (lines 1538-1703)."""
    device_name = f"{state.site_name}-{device['name']}"
    obj = state.device_nodes[device_name]

    l3_interface_batch = await ctx.client.create_batch()
    address_batch = await ctx.client.create_batch()
    circuit_batch = await ctx.client.create_batch()
    endpoint_batch = await ctx.client.create_batch()
    bgp_session_batch = await ctx.client.create_batch()

    # `provider` mirrors the script's loop-scoped variable: assigned only in the `upstream`
    # branch, deliberately STALE in the `peering` branch (see module docstring).
    provider_id: str | None = None

    for intf_idx, intf_name in enumerate(INTERFACE_L3_NAMES.get(device["type"], [])):
        intf_role = INTERFACE_L3_ROLES_MAPPING[device["role"]][intf_idx]

        intf = await ctx.client.create(
            branch=BRANCH,
            kind="InfraInterfaceL3",
            device={"id": obj.id, "is_protected": True},
            name=intf_name,
            speed=10000,
            enabled=True,
            status={"value": ACTIVE_STATUS, "owner": ctx.group_ops_id},
            role={"value": intf_role, "source": ctx.account_pop_id},
        )
        l3_interface_batch.add(task=intf.save, node=intf)
        state.l3_interfaces[f"{device_name}-l3-{intf_idx}"] = intf

        interface_identifier = f"{intf.name.value.lower()}.{device_name}"

        # Determine the IP address (if any) for this interface.
        address = None
        peer_address = None  # For roles that require a peer IP

        if "edge" in device["role"]:
            if intf_role == "backbone":
                state.backbone_interfaces.setdefault(device_name, []).append(intf)

            if intf_role == "peer":
                address = f"{next(state.peer_network_hosts[device['idx']][intf_idx])!s}/31"

            if intf_role in {"upstream", "peering"}:
                prefix_identifier = f"{intf_role}: {intf.name.value}.{device_name}"
                subnet = await ctx.client.allocate_next_ip_prefix(
                    kind="IpamIPPrefix",  # type: ignore[call-overload]
                    resource_pool=ctx.external_pool,
                    identifier=prefix_identifier,
                    data={"description": {"value": prefix_identifier, "source": ctx.account_pop_id}},
                    branch=BRANCH,
                )
                subnet_hosts = subnet.prefix.value.hosts()
                address = f"{next(subnet_hosts)!s}/29"
                peer_address = f"{next(subnet_hosts)!s}/29"

        ip = None
        if address:
            ip = await ctx.client.create(
                branch=BRANCH,
                kind="IpamIPAddress",
                interface=intf,
                address={"value": address, "source": ctx.account_pop_id},
                description={"value": interface_identifier, "source": ctx.account_pop_id},
            )
            address_batch.add(task=ip.save, node=ip, allow_upsert=True)

        # Create Circuit and BGP session for upstream and peering
        if intf_role in {"upstream", "peering"}:
            circuit_id_unique = _deterministic_circuit_id_unique(f"{device_name}-{intf_role}-{address}")
            circuit_id = f"DUFF-{circuit_id_unique}"
            bgp_session = None

            if intf_role == "upstream":
                provider_name = UPSTREAM_PROVIDERS[intf_idx % 2]
                provider_id = ctx.organizations[provider_name]

                # Script line 1623 checks the provider NODE's name; the store key IS the name.
                peer_group_name = "UPSTREAM_ARELION" if "arelion" in provider_name.lower() else "UPSTREAM_DEFAULT"

                peer_ip = await ctx.client.create(
                    branch=BRANCH,
                    kind="IpamIPAddress",
                    address=peer_address,
                )
                address_batch.add(task=peer_ip.save, node=peer_ip, allow_upsert=True)
                session_description = f"external-{ip.address.value.ip}-{peer_ip.address.value.ip}"
                bgp_session = await ctx.client.create(
                    branch=BRANCH,
                    kind="InfraBGPSession",
                    type="EXTERNAL",
                    description=session_description,
                    local_as=ctx.internal_as_id,
                    local_ip=ip,
                    remote_as=ctx.asns[provider_name],
                    remote_ip=peer_ip,
                    peer_group=ctx.peer_groups[peer_group_name],
                    device=state.device_nodes[device_name].id,
                    status=ACTIVE_STATUS,
                    role=intf_role,
                )
                bgp_session_batch.add(task=bgp_session.save, node=bgp_session)

            elif intf_role == "peering":
                # SCRIPT BUG preserved (lines 1656-1657): only provider_NAME is reassigned;
                # provider_id still holds Colt Technology Services from the Ethernet6 upstream.
                provider_name = "Equinix"

            circuit_data: dict[str, Any] = {
                "circuit_id": circuit_id,
                "vendor_id": f"{provider_name.upper()}-{UUIDT().short()}",
                "provider": provider_id,
                "status": {"value": ACTIVE_STATUS, "owner": ctx.group_ops_id},
                "role": {"value": intf_role, "source": ctx.account_pop_id, "owner": ctx.group_eng_id},
            }
            if bgp_session:
                circuit_data["bgp_sessions"] = [bgp_session]

            circuit = await ctx.client.create(branch=BRANCH, kind="InfraCircuit", data=circuit_data)
            circuit_batch.add(task=circuit.save, node=circuit)

            endpoint1 = await ctx.client.create(
                branch=BRANCH,
                kind="InfraCircuitEndpoint",
                site=state.site_obj,
                circuit=circuit,
                connected_endpoint=intf,
            )
            endpoint_batch.add(task=endpoint1.save, node=endpoint1)

            intf.description.value = f"Connected to {provider_name} via {circuit_id}"

    # Batch execution order mirrors lines 1692-1703 (the never-filled cable_batch is dropped).
    async for _ in l3_interface_batch.execute():
        pass
    async for _ in address_batch.execute():
        pass
    async for _ in bgp_session_batch.execute():
        pass
    async for _ in circuit_batch.execute():
        pass
    async for _ in endpoint_batch.execute():
        pass


async def _create_l2_and_lag_interfaces(ctx: _SiteContext, state: _SiteState, device: dict[str, Any]) -> None:
    """Transcribes the L2 interface and LAG blocks of ``generate_site`` (lines 1705-1778)."""
    device_name = f"{state.site_name}-{device['name']}"
    obj = state.device_nodes[device_name]

    # L2 Interfaces
    l2_interface_batch = await ctx.client.create_batch()

    for intf_idx, intf_name in enumerate(INTERFACE_L2_NAMES.get(device["type"], [])):
        try:
            intf_role = INTERFACE_L2_ROLES_MAPPING.get(device["role"], [])[intf_idx]
        except IndexError:
            intf_role = "server"

        l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

        untagged_vlan = None
        if l2_mode == "Access":
            untagged_vlan = state.vlans[f"{state.site_name}_server"]

        intf = await ctx.client.create(
            branch=BRANCH,
            kind="InfraInterfaceL2",
            device={"id": obj.id, "is_protected": True},
            name=intf_name,
            speed=10000,
            enabled=True,
            status={"value": ACTIVE_STATUS, "owner": ctx.group_ops_id},
            role={"value": intf_role, "source": ctx.account_pop_id},
            l2_mode=l2_mode,
            untagged_vlan=untagged_vlan,
        )
        l2_interface_batch.add(task=intf.save, node=intf)
        state.l2_interfaces[f"{device_name}-l2-{intf_name}"] = intf

    async for _ in l2_interface_batch.execute():
        pass

    for lag_intf in LAG_INTERFACE_L2.get(device["type"], []):
        try:
            intf_role = LAG_INTERFACE_L2_ROLES_MAPPING[device["role"]][lag_intf["name"]]
        except KeyError:
            intf_role = "server"

        l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

        description = lag_intf.get("description", "")

        untagged_vlan = None
        if l2_mode == "Access":
            untagged_vlan = state.vlans[f"{state.site_name}_server"]

        lag = await ctx.client.create(
            branch=BRANCH,
            kind="InfraLagInterfaceL2",
            device={"id": obj.id, "is_protected": True},
            name=lag_intf["name"],
            description=description,
            speed=10000,
            enabled=True,
            l2_mode=l2_mode,
            untagged_vlan=untagged_vlan,
            status={"value": ACTIVE_STATUS, "owner": ctx.group_ops_id},
            role={"value": intf_role, "source": ctx.account_pop_id},
            lacp=lag_intf["lacp"],
        )
        await lag.save()
        state.lag_interfaces[f"{device_name}-lagl2-{lag_intf['name']}"] = lag

        members = [state.l2_interfaces[f"{device_name}-l2-{member}"].id for member in lag_intf["members"]]
        await lag.add_relationships(relation_to_update="members", related_nodes=members)


async def _generate_site_mlag_domain(ctx: _SiteContext, state: _SiteState) -> None:
    """Transcribes ``generate_site_mlag_domain`` (lines 1332-1381).

    The script passes no ``branch`` here (client default, "main" under infrahubctl);
    made explicit for uniformity.
    """
    # Set up MLAG domains
    for role, domain in MLAG_DOMAINS.items():
        devices = [
            state.device_nodes[f"{state.site_name}-{role}1"],
            state.device_nodes[f"{state.site_name}-{role}2"],
        ]
        name = f"{state.site_name}-{role}-12"

        peer_interfaces = [
            state.lag_interfaces[f"{device_obj.name.value}-lagl2-{domain['peer_interfaces'][idx]}"]
            for idx, device_obj in enumerate(devices)
        ]

        mlag_domain = await ctx.client.create(
            branch=BRANCH,
            kind="InfraMlagDomain",
            name=name,
            domain_id=domain["domain_id"],
            devices=devices,
            peer_interfaces=peer_interfaces,
        )
        await mlag_domain.save()
        state.mlag_domains[f"mlag-domain-{name}"] = mlag_domain

    # Set up MLAG Interfaces
    for role, mlags in MLAG_INTERFACE_L2.items():
        devices = [
            state.device_nodes[f"{state.site_name}-{role}1"],
            state.device_nodes[f"{state.site_name}-{role}2"],
        ]

        for mlag in mlags:
            members = [
                state.lag_interfaces[f"{device_obj.name.value}-lagl2-{mlag['members'][idx]}"]
                for idx, device_obj in enumerate(devices)
            ]
            mlag_domain = state.mlag_domains[f"mlag-domain-{state.site_name}-{role}-12"]

            mlag_interface = await ctx.client.create(
                branch=BRANCH,
                kind="InfraMlagInterfaceL2",
                mlag_domain=mlag_domain,
                mlag_id=mlag["mlag_id"],
                members=members,
            )
            await mlag_interface.save()


def _find_and_connect_interfaces(  # noqa: PLR0913, PLR0917  (mirrors the script function's signature)
    batch: InfrahubBatch,
    interfaces: dict[str, InfrahubNode],
    first_device_name: str,
    first_interface_key: str,
    second_device_name: str,
    second_interface_key: str,
) -> None:
    """Transcribes ``find_and_connect_interfaces``: set BOTH symmetric sides, save the pair sequentially."""
    first_interface = interfaces[first_interface_key]
    second_interface = interfaces[second_interface_key]

    first_interface.description.value = f"Connected to {second_device_name}::{second_interface.name.value}"
    first_interface.connected_endpoint = second_interface  # type: ignore[assignment]

    # `connected_endpoint` is a SYMMETRIC peer relationship: set it explicitly on this side
    # too, otherwise saving the second interface with an unset peer clears the link the first
    # save just established (serialized loads, max_concurrent_execution=1).
    second_interface.description.value = f"Connected to {first_device_name}::{first_interface.name.value}"
    second_interface.connected_endpoint = first_interface  # type: ignore[assignment]

    # One batch task saves both sides SEQUENTIALLY: saved concurrently (batch
    # concurrency > 1), each side's transaction misses the other's edge and the
    # node ends up with 2 peers, failing the card-one validation. Harmless at
    # this loader's concurrency of 1, but mirrors the script's fixed semantics.
    batch.add(
        task=_save_connected_pair,
        node=first_interface,
        first_interface=first_interface,
        second_interface=second_interface,
    )


async def _save_connected_pair(first_interface: InfrahubNode, second_interface: InfrahubNode) -> None:
    await first_interface.save()
    await second_interface.save()


async def _connect_site_cabling(ctx: _SiteContext, state: _SiteState) -> None:
    """Transcribes the edge/leaf pairing loops of ``generate_site`` (lines 1782-1842)."""
    batch_interface = await ctx.client.create_batch()

    # Connect edge devices 2 by 2 (L3 Ethernet1<->Ethernet1, Ethernet2<->Ethernet2)
    for idx in range(1, NUM_EDGE_DEVICE, 2):
        _find_and_connect_interfaces(
            batch=batch_interface,
            interfaces=state.l3_interfaces,
            first_device_name=f"{state.site_name}-edge{idx}",
            first_interface_key=f"{state.site_name}-edge{idx}-l3-0",
            second_device_name=f"{state.site_name}-edge{idx + 1}",
            second_interface_key=f"{state.site_name}-edge{idx + 1}-l3-0",
        )
        _find_and_connect_interfaces(
            batch=batch_interface,
            interfaces=state.l3_interfaces,
            first_device_name=f"{state.site_name}-edge{idx}",
            first_interface_key=f"{state.site_name}-edge{idx}-l3-1",
            second_device_name=f"{state.site_name}-edge{idx + 1}",
            second_interface_key=f"{state.site_name}-edge{idx + 1}-l3-1",
        )

    # Connect leaf devices 2 by 2 (L2 Ethernet1<->Ethernet1, Ethernet2<->Ethernet2)
    for idx in range(1, NUM_LEAF_DEVICE, 2):
        _find_and_connect_interfaces(
            batch=batch_interface,
            interfaces=state.l2_interfaces,
            first_device_name=f"{state.site_name}-leaf{idx}",
            first_interface_key=f"{state.site_name}-leaf{idx}-l2-Ethernet1",
            second_device_name=f"{state.site_name}-leaf{idx + 1}",
            second_interface_key=f"{state.site_name}-leaf{idx + 1}-l2-Ethernet1",
        )
        _find_and_connect_interfaces(
            batch=batch_interface,
            interfaces=state.l2_interfaces,
            first_device_name=f"{state.site_name}-leaf{idx}",
            first_interface_key=f"{state.site_name}-leaf{idx}-l2-Ethernet2",
            second_device_name=f"{state.site_name}-leaf{idx + 1}",
            second_interface_key=f"{state.site_name}-leaf{idx + 1}-l2-Ethernet2",
        )

    async for _ in batch_interface.execute():
        pass


async def _generate_site(ctx: _SiteContext, site: dict[str, str]) -> _SiteState:
    """Transcribes ``generate_site`` (lines 1384-1879) for one site."""
    # Create the Site
    site_obj = await ctx.client.create(
        branch=BRANCH,
        kind="LocationSite",
        name={"value": site["name"], "is_protected": True, "source": ctx.account_crm_id},
        contact={"value": site["contact"], "is_protected": True, "source": ctx.account_crm_id},
        city={"value": site["city"], "is_protected": True, "source": ctx.account_crm_id},
        parent=ctx.countries[site["country"]],
    )
    await site_obj.save()

    state = _SiteState(site_name=site["name"], site_obj=site_obj)

    await _generate_site_vlans(ctx=ctx, state=state)
    await _allocate_peer_networks(ctx=ctx, state=state)

    devices = _site_devices()
    await _create_devices(ctx=ctx, state=state, devices=devices)

    # Create interfaces for each device, in pattern order (edge1..leaf2): the allocation
    # order across sites and devices is what the deterministic IP assertions depend on.
    for device in devices:
        await _create_loopback_and_management(ctx=ctx, state=state, device=device)
        await _create_l3_interfaces(ctx=ctx, state=state, device=device)
        await _create_l2_and_lag_interfaces(ctx=ctx, state=state, device=device)

    await _generate_site_mlag_domain(ctx=ctx, state=state)
    await _connect_site_cabling(ctx=ctx, state=state)

    return state


@pytest.fixture(scope="session")
async def data_sites(  # noqa: PLR0913, PLR0917  (each argument is a pytest fixture dependency)
    data_client: InfrahubClient,
    schema_base: None,
    data_rbac: RbacHandle,
    data_locations: LocationsHandle,
    data_org_registry: OrgRegistryHandle,
    data_ipam_pools: IpamPoolsHandle,
    infrahub_provisioned_externally: bool,
) -> SitesHandle:
    """The five sites and everything ``generate_site`` created inside them."""
    if infrahub_provisioned_externally:
        return SitesHandle.external()

    # The resource-pool NODES generate_site allocates from (the script passed the created
    # pool objects straight through run(); here they are refetched once from the handle ids).
    ctx = _SiteContext(
        client=data_client,
        account_pop_id=data_rbac.accounts["pop-builder"],
        account_crm_id=data_rbac.accounts["crm-sync"],
        group_eng_id=data_rbac.groups["eng-team"],
        group_ops_id=data_rbac.groups["ops-team"],
        internal_as_id=data_org_registry.asns["Duff"],
        asns=data_org_registry.asns,
        peer_groups=data_org_registry.peer_groups,
        organizations=data_org_registry.organizations,
        tags=data_org_registry.tags,
        platforms=data_org_registry.platforms,
        countries=data_locations.countries,
        interconnection_pool=await data_client.get(
            kind="CoreIPPrefixPool", id=data_ipam_pools.pools["Interconnections pool"]
        ),
        loopback_pool=await data_client.get(kind="CoreIPAddressPool", id=data_ipam_pools.pools["Loopbacks pool"]),
        management_pool=await data_client.get(
            kind="CoreIPAddressPool", id=data_ipam_pools.pools["Management addresses pool"]
        ),
        external_pool=await data_client.get(
            kind="CoreIPPrefixPool", id=data_ipam_pools.pools["External prefixes pool"]
        ),
    )

    sites: dict[str, str] = {}
    devices: dict[str, str] = {}
    loopback_ips: dict[str, str] = {}
    backbone_interface_ids: dict[str, list[str]] = {}
    vlans: dict[str, str] = {}

    for site in _site_generator(nbr_site=NUM_SITES):
        state = await _generate_site(ctx=ctx, site=site)
        sites[state.site_name] = state.site_obj.id
        devices.update({name: node.id for name, node in state.device_nodes.items()})
        loopback_ips.update(state.loopback_ips)
        # Ids are read only here, after every batch of the site has executed.
        backbone_interface_ids.update(
            {name: [node.id for node in nodes] for name, nodes in state.backbone_interfaces.items()}
        )
        vlans.update({key: node.id for key, node in state.vlans.items()})

    return SitesHandle(
        sites=sites,
        devices=devices,
        loopback_ips=loopback_ips,
        backbone_interface_ids=backbone_interface_ids,
        vlans=vlans,
    )
