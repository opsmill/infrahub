"""Topology slice: interface profiles & groups, device groups, iBGP full mesh, backbone links.

Faithful transcription of the cross-site stage of ``models/infrastructure_edge.py``,
in the order ``run()`` calls it after the per-site loop (lines 2801-2815):

* ``apply_interface_profiles_and_groups`` (lines 913-986): server-side filters
  for the upstream/backbone-role L3 interfaces (``Order(disable=True)``), one
  batch of per-interface ``add_relationships(relation_to_update="profiles")``
  calls, then one ``add_relationships(relation_to_update="members")`` per
  standard group (``upstream_interfaces`` / ``backbone_interfaces``),
* ``apply_devices_groups`` (lines 989-1094): all devices fetched with
  ``prefetch_relationships``, grouped by role (edge_router, core_router) and
  platform vendor (arista_devices, cisco_devices); the script's leaf_switch /
  juniper_devices groupings are commented out and stay out,
* ``create_bgp_mesh`` (lines 1234-1290, ``has_bgp_mesh=True`` at the medium
  profile): for every ordered pair of distinct sites and every edge index
  pair in ``range(1, min(3, num_sites))`` an INTERNAL InfraBGPSession
  (local/remote AS = Duff, local/remote IP = the devices' Loopback0
  addresses, peer group POP_GLOBAL, device = the local edge) — 5x4x2x2 = 80
  sessions saved in a single batch,
* ``create_backbone_connectivity`` (lines 1097-1231): the ``P2P_NETWORKS``
  table (lines 1115-1122, num_sites guards included), one /31 per link from
  the Interconnections pool with identifier
  ``"<site1>-edge<e>__<site2>-edge<e>"``, then per link a backbone
  InfraCircuit + 2 InfraCircuitEndpoints + the 2 host IPs (descriptions
  ``"<intf>.<device>"``), the immediate interface-description saves
  (``"Backbone: Connected to <device> via <circuit>"``), the immediate
  ``InfraBackBoneService`` upserts and finally the circuit/endpoint/IP batch
  executions in that order.

Deviations:

* async SDK with kind STRINGS instead of generated protocol classes; nodes the
  script read from ``client.store`` come from the upstream handles instead,
* the script's module-global ``INTERFACE_OBJS`` becomes
  ``data_sites.backbone_interface_ids``: a mutable copy is consumed with
  ``pop(0)`` (same order), and each popped interface is refetched by id with
  ``include=["device"]`` — the same ``client.get`` the script performs for
  the description update (it populates the store, so ``device.peer`` resolves
  exactly as in the script),
* the mesh resolves loopback IpamIPAddress node ids by address value (the
  handle carries address VALUES; the script kept the nodes in
  ``client.store``) — one lookup per edge device, then ids are passed to
  ``local_ip``/``remote_ip`` like the script did,
* ``branch="main"`` is passed explicitly where the script relied on the
  client's default branch (the ``InfraBackBoneService`` create),
* vendor ids keep the script's non-deterministic ``UUIDT().short()``,
* log-only code is dropped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.types import Order
from infrahub_sdk.uuidt import UUIDT

from data.common import save_with_retry
from data.handles import TopologyHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from data.handles import (
        IpamPoolsHandle,
        OrgRegistryHandle,
        ProfilesGroupsHandle,
        RbacHandle,
        SitesHandle,
    )

BRANCH = "main"

# (lines 567-568)
ACTIVE_STATUS = "active"
BACKBONE_ROLE = "backbone"


def _p2p_networks(num_sites: int) -> list[dict[str, str | int]]:
    """Transcribes the ``p2p_networks`` table of ``create_backbone_connectivity`` (lines 1113-1122)."""
    p2p_networks: list[dict[str, str | int]] = []

    if num_sites > 1:
        p2p_networks.extend(
            (
                {"site1": "atl1", "site2": "ord1", "edge": 1, "circuit": "DUFF-1543451"},
                {"site1": "atl1", "site2": "ord1", "edge": 2, "circuit": "DUFF-8263953"},
            )
        )
    if num_sites > 2:
        p2p_networks.extend(
            (
                {"site1": "atl1", "site2": "jfk1", "edge": 1, "circuit": "DUFF-6535773"},
                {"site1": "atl1", "site2": "jfk1", "edge": 2, "circuit": "DUFF-7324064"},
                {"site1": "jfk1", "site2": "ord1", "edge": 1, "circuit": "DUFF-5826854"},
                {"site1": "jfk1", "site2": "ord1", "edge": 2, "circuit": "DUFF-4867430"},
            )
        )

    return p2p_networks


def _provider_name(edge: int) -> str:
    """Transcribes ``P2pNetwork.provider_name`` (lines 283-287): edge1 links are Lumen, edge2 Zayo."""
    if edge == 1:
        return "Lumen"
    return "Zayo"


async def _apply_interface_profiles_and_groups(client: InfrahubClient, interface_profiles: dict[str, str]) -> None:
    """Transcribes ``apply_interface_profiles_and_groups`` (lines 913-986)."""
    # Fetch upstream and backbone interfaces.
    upstream_interfaces = await client.filters(
        branch=BRANCH,
        kind="InfraInterfaceL3",
        role__value="upstream",
        order=Order(disable=True),
    )
    backbone_interfaces = await client.filters(
        branch=BRANCH,
        kind="InfraInterfaceL3",
        role__value="backbone",
        order=Order(disable=True),
    )

    upstream_profile_id = interface_profiles["upstream_profile"]
    backbone_profile_id = interface_profiles["backbone_profile"]

    # Apply profiles using batch processing.
    batch = await client.create_batch()
    for interface in upstream_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[upstream_profile_id],
        )
    for interface in backbone_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[backbone_profile_id],
        )
    async for _ in batch.execute():
        pass

    # Update interface groups.
    if upstream_interfaces:
        group_upstream_interfaces = await client.get(
            kind="CoreStandardGroup",
            name__value="upstream_interfaces",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        upstream_interface_ids = [interface.id for interface in upstream_interfaces]
        await group_upstream_interfaces.add_relationships(
            relation_to_update="members", related_nodes=upstream_interface_ids
        )
    if backbone_interfaces:
        group_backbone_interfaces = await client.get(
            kind="CoreStandardGroup",
            name__value="backbone_interfaces",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        backbone_interface_ids = [interface.id for interface in backbone_interfaces]
        await group_backbone_interfaces.add_relationships(
            relation_to_update="members", related_nodes=backbone_interface_ids
        )


async def _apply_devices_groups(client: InfrahubClient) -> None:
    """Transcribes ``apply_devices_groups`` (lines 989-1094).

    The leaf_switch / juniper_devices groupings are commented out in the script
    (their member lists always stay empty), so only the four live groups are updated.
    """
    devices = await client.filters(
        branch=BRANCH,
        kind="InfraDevice",
        include=["name", "role", "platform"],
        prefetch_relationships=True,
        order=Order(disable=True),
    )

    # Initialize lists for grouping by role.
    group_core_router_members: list[str] = []
    group_edge_router_members: list[str] = []

    # Initialize lists for grouping by manufacturer/platform.
    group_arista_devices_members: list[str] = []
    group_cisco_devices_members: list[str] = []

    for device in devices:
        device_role = device.role.value
        if "edge" in device_role:
            group_edge_router_members.append(device.id)
        elif "core" in device_role:
            group_core_router_members.append(device.id)

        if "Arista" in device.platform.peer.name.value:
            group_arista_devices_members.append(device.id)
        elif "Cisco" in device.platform.peer.name.value:
            group_cisco_devices_members.append(device.id)

    # Update device groups.
    if group_edge_router_members:
        group_edge_router = await client.get(
            kind="CoreStandardGroup",
            name__value="edge_router",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_edge_router.add_relationships(relation_to_update="members", related_nodes=group_edge_router_members)
    if group_core_router_members:
        group_core_router = await client.get(
            kind="CoreStandardGroup",
            name__value="core_router",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_core_router.add_relationships(relation_to_update="members", related_nodes=group_core_router_members)
    if group_arista_devices_members:
        group_arista_devices = await client.get(
            kind="CoreStandardGroup",
            name__value="arista_devices",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_arista_devices.add_relationships(
            relation_to_update="members", related_nodes=group_arista_devices_members
        )
    if group_cisco_devices_members:
        group_cisco_devices = await client.get(
            kind="CoreStandardGroup",
            name__value="cisco_devices",
            branch=BRANCH,
            include=["members"],
            prefetch_relationships=True,
        )
        await group_cisco_devices.add_relationships(
            relation_to_update="members", related_nodes=group_cisco_devices_members
        )


async def _create_bgp_mesh(  # noqa: PLR0913, PLR0917
    client: InfrahubClient,
    site_names: list[str],
    devices: dict[str, str],
    loopback_ips: dict[str, str],
    internal_as_id: str,
    peer_group_id: str,
) -> int:
    """Transcribes ``create_bgp_mesh`` (lines 1234-1290): 80 INTERNAL sessions in one batch."""
    num_sites = len(site_names)

    # The script read the loopback nodes from client.store; resolve them once per edge
    # device from the handle's address values instead (loopback addresses are unique).
    loopback_node_ids: dict[str, str] = {}

    async def loopback_id(device_name: str) -> str:
        if device_name not in loopback_node_ids:
            node = await client.get(kind="IpamIPAddress", address__value=loopback_ips[device_name], branch=BRANCH)
            loopback_node_ids[device_name] = node.id
        return loopback_node_ids[device_name]

    batch = await client.create_batch()
    sessions = 0

    for site1 in site_names:
        for site2 in site_names:
            if site1 == site2:
                continue

            for idx1 in range(1, min(3, num_sites)):
                for idx2 in range(1, min(3, num_sites)):
                    device1 = f"{site1}-edge{idx1}"
                    device2 = f"{site2}-edge{idx2}"

                    obj = await client.create(
                        branch=BRANCH,
                        kind="InfraBGPSession",
                        type="INTERNAL",
                        local_as=internal_as_id,
                        local_ip=await loopback_id(device1),
                        remote_as=internal_as_id,
                        remote_ip=await loopback_id(device2),
                        peer_group=peer_group_id,
                        device=devices[device1],
                        status=ACTIVE_STATUS,
                        role=BACKBONE_ROLE,
                    )
                    batch.add(task=save_with_retry, node=obj, obj=obj)
                    sessions += 1

    async for _ in batch.execute():
        pass

    return sessions


async def _create_backbone_connectivity(  # noqa: PLR0913, PLR0914, PLR0917  (transcribed script function, one local per created node)
    client: InfrahubClient,
    num_sites: int,
    backbone_interface_ids: dict[str, list[str]],
    account_pop_id: str,
    interconnection_pool_id: str,
    organizations: dict[str, str],
) -> tuple[str, ...]:
    """Transcribes ``create_backbone_connectivity`` (lines 1097-1231)."""
    interconnection_pool = await client.get(kind="CoreIPPrefixPool", id=interconnection_pool_id, branch=BRANCH)

    # The script's INTERFACE_OBJS: per edge device the ordered [Ethernet3, Ethernet4]
    # interface ids, consumed with pop(0) link by link.
    interface_queue = {device: list(ids) for device, ids in backbone_interface_ids.items()}

    p2p_networks = _p2p_networks(num_sites=num_sites)

    pools: list = []
    for network in p2p_networks:
        identifier = f"{network['site1']}-edge{network['edge']}__{network['site2']}-edge{network['edge']}"
        pools.append(
            await client.allocate_next_ip_prefix(
                resource_pool=interconnection_pool,
                kind="IpamIPPrefix",  # type: ignore[call-overload]
                branch=BRANCH,
                identifier=identifier,
            )
        )

    circuit_batch = await client.create_batch()
    endpoint_batch = await client.create_batch()
    interface_ip_batch = await client.create_batch()
    service_names: list[str] = []

    for backbone_link, pool in zip(p2p_networks, pools, strict=True):
        site1_device = f"{backbone_link['site1']}-edge{backbone_link['edge']}"
        site2_device = f"{backbone_link['site2']}-edge{backbone_link['edge']}"

        intf_site1_id = interface_queue[site1_device].pop(0)
        intf_site1_obj = await client.get(id=intf_site1_id, include=["device"], kind="InfraInterfaceL3", branch=BRANCH)
        intf_site2_id = interface_queue[site2_device].pop(0)
        intf_site2_obj = await client.get(id=intf_site2_id, include=["device"], kind="InfraInterfaceL3", branch=BRANCH)

        backbone_link_ips = pool.prefix.value.hosts()

        provider_name = _provider_name(edge=int(backbone_link["edge"]))
        provider_id = organizations[provider_name]
        vendor_id = f"{provider_name}-{UUIDT().short()}"
        bkb_circuit = await client.create(
            branch=BRANCH,
            kind="InfraCircuit",
            description=f"BKB: {backbone_link['site1']} <-> {backbone_link['site2']}",
            circuit_id=backbone_link["circuit"],
            vendor_id=vendor_id.upper(),
            provider=provider_id,
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        circuit_batch.add(task=save_with_retry, node=bkb_circuit, obj=bkb_circuit)

        # Create Circuit Endpoints. NB: like the script, `site` is the site NAME — the
        # backend resolves non-UUID relationship ids through the kind's default filter.
        endpoint1 = await client.create(
            branch=BRANCH,
            kind="InfraCircuitEndpoint",
            description=f"Endpoint {backbone_link['circuit']} to {site1_device}",
            site=backbone_link["site1"],
            circuit=bkb_circuit,
            connected_endpoint=intf_site1_obj,
        )
        endpoint_batch.add(task=save_with_retry, node=endpoint1, obj=endpoint1)

        endpoint2 = await client.create(
            branch=BRANCH,
            kind="InfraCircuitEndpoint",
            description=f"Endpoint {backbone_link['circuit']} to {site2_device}",
            site=backbone_link["site2"],
            circuit=bkb_circuit,
            connected_endpoint=intf_site2_obj,
        )
        endpoint_batch.add(task=save_with_retry, node=endpoint2, obj=endpoint2)

        # Create IP Address
        intf_site1_address = f"{next(backbone_link_ips)!s}/31"
        intf_site2_address = f"{next(backbone_link_ips)!s}/31"
        intf_site1_identifier = f"{intf_site1_obj.name.value.lower()}.{intf_site1_obj.device.peer.name.value}"
        intf_site2_identifier = f"{intf_site2_obj.name.value.lower()}.{intf_site2_obj.device.peer.name.value}"
        intf_site1_ip = await client.create(
            branch=BRANCH,
            kind="IpamIPAddress",
            interface={"id": intf_site1_id, "source": account_pop_id},
            address={"value": intf_site1_address, "source": account_pop_id},
            description={"value": intf_site1_identifier, "source": account_pop_id},
        )
        interface_ip_batch.add(task=save_with_retry, node=intf_site1_ip, obj=intf_site1_ip)

        intf_site2_ip = await client.create(
            branch=BRANCH,
            kind="IpamIPAddress",
            interface={"id": intf_site2_id, "source": account_pop_id},
            address={"value": intf_site2_address, "source": account_pop_id},
            description={"value": intf_site2_identifier, "source": account_pop_id},
        )
        interface_ip_batch.add(task=save_with_retry, node=intf_site2_ip, obj=intf_site2_ip)

        # Update Interface (immediate saves, like the script)
        intf_site1_obj.description.value = f"Backbone: Connected to {site2_device} via {backbone_link['circuit']}"
        await intf_site1_obj.save()

        intf_site2_obj.description.value = f"Backbone: Connected to {site1_device} via {backbone_link['circuit']}"
        await intf_site2_obj.save()

        service_name = f"BKB: {backbone_link['site1']} <-> {backbone_link['site2']}"
        bb_service = await client.create(
            branch=BRANCH,
            kind="InfraBackBoneService",
            name=service_name,
            circuit_id=backbone_link["circuit"],
            internal_circuit_id=vendor_id.upper(),
            provider=provider_id,
            site_a=backbone_link["site1"],
            site_b=backbone_link["site2"],
        )
        await bb_service.save(allow_upsert=True)
        service_names.append(service_name)

    async for _ in circuit_batch.execute():
        pass
    async for _ in endpoint_batch.execute():
        pass
    async for _ in interface_ip_batch.execute():
        pass

    return tuple(service_names)


@pytest.fixture(scope="session")
async def data_topology(  # noqa: PLR0913, PLR0917  (each argument is a pytest fixture dependency)
    data_client: InfrahubClient,
    schema_base: None,
    data_sites: SitesHandle,
    data_rbac: RbacHandle,
    data_org_registry: OrgRegistryHandle,
    data_ipam_pools: IpamPoolsHandle,
    data_profiles_groups: ProfilesGroupsHandle,
    infrahub_provisioned_externally: bool,
) -> TopologyHandle:
    """Profiles/groups applied, the 80-session iBGP mesh and the 6 backbone links."""
    if infrahub_provisioned_externally:
        return TopologyHandle.external()

    await _apply_interface_profiles_and_groups(
        client=data_client, interface_profiles=data_profiles_groups.interface_profiles
    )
    await _apply_devices_groups(client=data_client)

    internal_sessions = await _create_bgp_mesh(
        client=data_client,
        site_names=list(data_sites.sites),
        devices=data_sites.devices,
        loopback_ips=data_sites.loopback_ips,
        internal_as_id=data_org_registry.asns["Duff"],
        peer_group_id=data_org_registry.peer_groups["POP_GLOBAL"],
    )

    backbone_services = await _create_backbone_connectivity(
        client=data_client,
        num_sites=len(data_sites.sites),
        backbone_interface_ids=data_sites.backbone_interface_ids,
        account_pop_id=data_rbac.accounts["pop-builder"],
        interconnection_pool_id=data_ipam_pools.pools["Interconnections pool"],
        organizations=data_org_registry.organizations,
    )

    return TopologyHandle(backbone_services=backbone_services, internal_sessions=internal_sessions)
