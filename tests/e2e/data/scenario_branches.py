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

These two scenarios ran on ord1/jfk1, which the 2-site slim no longer builds
(see data/sites.py KEPT_SITES), so there is nothing to drop — they simply do
not exist. The earlier ``_consume_dropped_scenario_pool_allocations`` ballast
(which replayed their branch-agnostic pool consumption to hold the external
next-free at 203.111.0.248/29 for
tests/e2e/ipam/test_ip_prefix_create_with_pool.py) was removed with the slim;
that test's next-free assertion is re-pinned to the 2-site value instead.

Other deviations from the script:

* The script runs all five scenarios CONCURRENTLY in one SDK batch; this
  fixture runs its three sequentially. End state is equivalent, and the branch
  points become deterministic — in the script a branch could be cut before or
  after another scenario's main-side mutations.
* Async SDK with kind STRINGS instead of generated protocol classes.
* ``branch="main"`` is passed explicitly where the script relied on the
  client's default branch (infrahubctl runs with default_branch "main").
* Log-only code is not transcribed: the ``circuit_id`` variable of
  remove_colt (only fed a log line) and the dangling no-op expression
  ``f"{site_name}-edge2"`` of conflict_device.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from data.handles import ScenarioBranchesHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from data.handles import PatchTemplateHandle, SitesHandle, TopologyHandle

BRANCH = "main"

# run() dispatch (lines 2827-2857): sites = site_generator(nbr_site=5) -> ["atl1", "ord1", "jfk1", "den1", "dfw1"].
REMOVE_COLT_SITE = "atl1"  # script sites[0]
CONFLICT_DEVICE_SITE = "den1"  # script sites[3]; the 2nd (last) built site under the slim
# Dropped scenarios add_upstream (script sites[1]=ord1) and replace_ip_addresses (sites[2]=jfk1)
# are not replayed: with the 2-site slim ord1/jfk1 are never built (see data/sites.py KEPT_SITES).

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

    # The three scenarios are independent: each creates its OWN branch off the
    # (already final) main and only mutates that branch, so they run
    # concurrently. (The dropped scenarios' pool ballast was removed with the
    # 2-site slim — ord1/jfk1 are no longer built at all, so there is nothing to
    # replay; the dependent test_ip_prefix_create_with_pool next-free assertion
    # was re-pinned to the 2-site value.)
    await asyncio.gather(
        _branch_scenario_remove_colt(client=data_client, site_name=REMOVE_COLT_SITE),
        _branch_scenario_conflict_device(client=data_client, site_name=CONFLICT_DEVICE_SITE),
        _branch_scenario_conflict_platform(client=data_client),
    )

    return ScenarioBranchesHandle(branches=SCENARIO_BRANCHES)
