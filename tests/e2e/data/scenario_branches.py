"""Scenario-branches slice: the demo branches tests exercise, cut from a fully loaded main.

Faithful transcription of three of the five branch scenarios of
``models/infrastructure_edge.py`` and their dispatch block in ``run()``
(lines ~2827-2857, which maps ``sites[0]``->atl1, ``sites[1]``->ord1,
``sites[2]``->jfk1, ``sites[3]``->den1):

* ``branch_scenario_remove_colt`` (lines 2051-2111, site atl1): branch
  ``atl1-delete-upstream``; query atl1's InfraCircuitEndpoints on the branch
  with the script's exact GraphQL query, keep those whose circuit provider is
  "Colt Technology Services", delete endpoint then circuit. The script's
  filter only looks at the provider, and generate_site attaches the Colt
  provider node to its peering circuits too (its ``peering`` branch sets
  ``provider_name = "Equinix"`` but never reassigns the ``provider`` variable,
  which still holds Colt from the preceding ``upstream`` interface), so FOUR
  circuits match per site (per edge device: the Colt upstream at Ethernet6
  plus the mislabeled peering at Ethernet9) — preserved as-is.
* ``branch_scenario_conflict_device`` (lines 2114-2152, site den1): branch
  ``den1-maintenance-conflict``; on the branch set den1-edge1
  status=maintenance and its Ethernet1 enabled=False + status=drained; then
  on MAIN set den1-edge1 status=provisioning and Ethernet1 enabled=False — a
  deliberate conflict. The main-side interface lookup reuses the BRANCH
  device node's id (script quirk, same node UUID on every branch; preserved).
* ``branch_scenario_conflict_platform`` (lines 2155-2185): branch
  ``platform-conflict``; create InfraPlatform "Cisco IOS XR"
  (netmiko_device_type=cisco_xr) on the branch AND on main (a node ADD
  conflict), delete "Cisco NXOS SSH" on the branch AND on main, delete
  "Juniper JunOS" on the branch but UPDATE it on main
  (nornir_platform=juniper_junos, was "junos") — a node DELETE/UPDATE conflict.

Dropped scenarios (deliberate — no e2e test references their branches):

* ``branch_scenario_add_upstream`` (lines 1882-1987, site ord1, branch
  ``ord1-add-upstream``),
* ``branch_scenario_replace_ip_addresses`` (lines 1990-2048, site jfk1,
  branch ``jfk1-update-edge-ips``).

Allocation ballast for the dropped scenarios
--------------------------------------------
Both dropped scenarios allocate from a shared resource pool ON THEIR BRANCH:
add_upstream takes the next /29 from the "External prefixes pool"
(identifier ``ord1-edge1``) and replace_ip_addresses takes the next /31 from
the "Interconnections pool" (identifier ``jfk1-edge1__jfk1-edge2``). Pool
next-free computation is branch-AGNOSTIC (``CoreIPPrefixPool.get_next`` uses
``IPAMResourceAllocator(..., branch_agnostic=True)``, see
backend/infrahub/core/node/resource_manager/ip_prefix_pool.py), so those
branch-scoped allocations consume pool space visible from every branch:
after the monolith load the next free external /29 is 203.111.0.248/29 —
exactly what tests/e2e/ipam/test_ip_prefix_create_with_pool.py asserts on a
throwaway branch cut from main. Dropping the scenarios without replacing the
consumption would shift that to 203.111.0.240/29 and break the test, so
``_consume_dropped_scenario_pool_allocations`` performs the SAME two
allocations (same pool, same identifier, no other kwargs) and creates no
branch and none of the branch-only objects (no circuits/IPs/interface edits).
It produces 203.111.0.240/29 (external, 31st /29 after the 30 generate_site
ones) and 10.1.0.32/31 (interconnections, 17th /31 after 10 generate_site +
6 backbone ones).

Known deviation of the ballast: it allocates with ``branch="main"`` while the
script allocated on the scenario branch, where the prefix NODE itself is
created (``get_resource`` inits the node on the mutation branch). On a
monolith-loaded stack the two prefixes therefore exist only on the dropped
branches and main shows them solely as consumed pool space; here they are
real nodes on main (main's IpamIPPrefix count is +2 vs the monolith parity
dump). Kept in a clearly separated function so it can be adjusted after the
first parity diff if the extra main-visible nodes matter.

Other deviations from the script:

* The script runs all five scenarios CONCURRENTLY in one SDK batch; this
  fixture runs its three sequentially in the dispatch order (ballast for the
  two dropped ones first, mirroring their batch.add positions). End state is
  equivalent, and the branch points become deterministic — in the script a
  branch could be cut before or after another scenario's main-side mutations.
* Async SDK with kind STRINGS instead of generated protocol classes.
* ``branch="main"`` is passed explicitly where the script relied on the
  client's default branch (infrahubctl runs with default_branch "main").
* Log-only code is not transcribed: the ``circuit_id`` variable of
  remove_colt (only fed a log line) and the dangling no-op expression
  ``f"{site_name}-edge2"`` of conflict_device.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from data.handles import ScenarioBranchesHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from data.handles import PatchTemplateHandle, SitesHandle, TopologyHandle

BRANCH = "main"

# run() dispatch (lines 2827-2857): sites = site_generator(nbr_site=5) -> ["atl1", "ord1", "jfk1", "den1", "dfw1"].
REMOVE_COLT_SITE = "atl1"  # sites[0]
CONFLICT_DEVICE_SITE = "den1"  # sites[3]
# Dropped scenarios (ballast only): add_upstream ran on sites[1], replace_ip_addresses on sites[2].
DROPPED_ADD_UPSTREAM_DEVICE = "ord1-edge1"
DROPPED_REPLACE_IP_DEVICES = ("jfk1-edge1", "jfk1-edge2")

SCENARIO_BRANCHES = ("atl1-delete-upstream", "den1-maintenance-conflict", "platform-conflict")

# Verbatim from branch_scenario_remove_colt (lines 2069-2094).
GET_CIRCUITS_QUERY = """
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


async def _consume_dropped_scenario_pool_allocations(client: InfrahubClient) -> None:
    """Replay the dropped scenarios' pool allocations (see module docstring).

    * branch_scenario_add_upstream line 1910: ``allocate_next_ip_prefix(
      resource_pool=external_pool, identifier=device_name, branch=new_branch_name)``
      with ``device_name = "ord1-edge1"`` -> 203.111.0.240/29.
    * branch_scenario_replace_ip_addresses line 2006: ``allocate_next_ip_prefix(
      kind=IpamIPPrefix, resource_pool=interconnection_pool,
      identifier=f"{device1_name}__{device2_name}", branch=new_branch_name)``
      -> 10.1.0.32/31.

    Allocated on main instead of the (not created) scenario branches; the
    identifiers make the calls idempotent (PrefixPoolGetReserved returns the
    reserved prefix on re-run).
    """
    external_pool = await client.get(kind="CoreIPPrefixPool", name__value="External prefixes pool", branch=BRANCH)
    await client.allocate_next_ip_prefix(
        resource_pool=external_pool, identifier=DROPPED_ADD_UPSTREAM_DEVICE, branch=BRANCH
    )

    interconnection_pool = await client.get(kind="CoreIPPrefixPool", name__value="Interconnections pool", branch=BRANCH)
    device1_name, device2_name = DROPPED_REPLACE_IP_DEVICES
    # NB: `kind` is typing-only sugar on allocate_next_ip_prefix (unused at runtime); mirrored from the script.
    await client.allocate_next_ip_prefix(
        kind="IpamIPPrefix",  # type: ignore[call-overload]
        resource_pool=interconnection_pool,
        identifier=f"{device1_name}__{device2_name}",
        branch=BRANCH,
    )


async def _branch_scenario_remove_colt(client: InfrahubClient, site_name: str) -> None:
    """Transcribes ``branch_scenario_remove_colt`` (lines 2051-2111)."""
    new_branch_name = f"{site_name}-delete-upstream"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Delete upstream circuit with colt in {site_name}",
    )

    circuits = await client.execute_graphql(
        branch_name=new_branch_name, query=GET_CIRCUITS_QUERY, variables={"site_name": site_name}
    )
    colt_circuits = [
        circuit
        for circuit in circuits["InfraCircuitEndpoint"]["edges"]
        if circuit["node"]["circuit"]["node"]["provider"]["node"]["name"]["value"] == "Colt Technology Services"
    ]

    for item in colt_circuits:
        circuit_endpoint = await client.get(branch=new_branch_name, kind="InfraCircuitEndpoint", id=item["node"]["id"])
        await circuit_endpoint.delete()

        circuit = await client.get(
            branch=new_branch_name, kind="InfraCircuit", id=item["node"]["circuit"]["node"]["id"]
        )
        await circuit.delete()


async def _branch_scenario_conflict_device(client: InfrahubClient, site_name: str) -> None:
    """Transcribes ``branch_scenario_conflict_device`` (lines 2114-2152)."""
    device1_name = f"{site_name}-edge1"

    new_branch_name = f"{site_name}-maintenance-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Put {device1_name} in maintenance mode",
    )

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

    device1_main = await client.get(branch=BRANCH, kind="InfraDevice", name__value=device1_name)

    device1_main.status.value = provisioning_status
    await device1_main.save()

    # The script looks the main-side interface up with the BRANCH device id (same node UUID).
    intf1_main = await client.get(
        branch=BRANCH, kind="InfraInterfaceL3", device__ids=[device1_branch.id], name__value="Ethernet1"
    )
    intf1_main.enabled.value = False
    await intf1_main.save()


async def _branch_scenario_conflict_platform(client: InfrahubClient) -> None:
    """Transcribes ``branch_scenario_conflict_platform`` (lines 2155-2185)."""
    new_branch_name = "platform-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description="Add new platform",
    )

    # Create a new Platform object with the same name, both in the branch and in main
    platform1_branch = await client.create(
        branch=new_branch_name, kind="InfraPlatform", name="Cisco IOS XR", netmiko_device_type="cisco_xr"
    )
    await platform1_branch.save()
    platform1_main = await client.create(
        branch=BRANCH, kind="InfraPlatform", name="Cisco IOS XR", netmiko_device_type="cisco_xr"
    )
    await platform1_main.save()

    # Delete an existing Platform object on both in the Branch and in Main
    platform2_branch = await client.get(branch=new_branch_name, kind="InfraPlatform", name__value="Cisco NXOS SSH")
    await platform2_branch.delete()
    platform2_main = await client.get(branch=BRANCH, kind="InfraPlatform", name__value="Cisco NXOS SSH")
    await platform2_main.delete()

    # Delete an existing Platform object in the branch and update it in main
    platform3_branch = await client.get(branch=new_branch_name, kind="InfraPlatform", name__value="Juniper JunOS")
    await platform3_branch.delete()
    platform3_main = await client.get(branch=BRANCH, kind="InfraPlatform", name__value="Juniper JunOS")
    platform3_main.nornir_platform.value = "juniper_junos"
    await platform3_main.save()


@pytest.fixture(scope="session")
async def data_scenario_branches(  # noqa: PLR0913, PLR0917  (each argument is a pytest fixture dependency)
    data_client: InfrahubClient,
    schema_base: None,
    data_sites: SitesHandle,
    data_topology: TopologyHandle,
    data_patch_template: PatchTemplateHandle,
    infrahub_provisioned_externally: bool,
) -> ScenarioBranchesHandle:
    """Cut the three scenario branches off the fully loaded main dataset.

    Depends on ``data_sites`` + ``data_topology`` + ``data_patch_template`` so
    the branches are created only once main carries the complete dataset —
    the script creates them last in ``run()``, and a branch snapshots main at
    creation time, so the ordering is what makes the branch contents match.
    """
    if infrahub_provisioned_externally:
        return ScenarioBranchesHandle.external()

    await _consume_dropped_scenario_pool_allocations(client=data_client)
    await _branch_scenario_remove_colt(client=data_client, site_name=REMOVE_COLT_SITE)
    await _branch_scenario_conflict_device(client=data_client, site_name=CONFLICT_DEVICE_SITE)
    await _branch_scenario_conflict_platform(client=data_client)

    return ScenarioBranchesHandle(branches=SCENARIO_BRANCHES)
