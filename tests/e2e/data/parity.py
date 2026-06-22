"""Dataset parity dump: a structural snapshot of a loaded Infrahub instance.

Used to prove that the SDK-fixture data slices reproduce the exact dataset the
monolithic ``models/infrastructure_edge.py`` script loads. Take one dump from a
stack loaded by the script and one from a stack loaded by the fixtures, then
diff the two JSON files:

    INFRAHUB_E2E_PARITY=monolith INFRAHUB_E2E_PARITY_OUT=/tmp/parity-monolith.json \
      uv run pytest -c tests/e2e/pytest.ini tests/e2e/data/test_parity_dump.py
    INFRAHUB_E2E_PARITY=fixtures INFRAHUB_E2E_PARITY_OUT=/tmp/parity-fixtures.json \
      uv run pytest -c tests/e2e/pytest.ini tests/e2e/data/test_parity_dump.py
    diff /tmp/parity-monolith.json /tmp/parity-fixtures.json

The dump deliberately excludes values that are non-deterministic in the script
(circuit ids derive from salted ``hash()``, vendor ids from UUIDs) and captures
structure instead: per-kind counts, display labels for the kinds tests select
by name, topology probes (interface counts, cabling pairs, group memberships,
BGP session types) and per-scenario-branch counts.
"""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient

# Kinds whose display labels tests select by name; sorted labels are dumped.
NAMED_KINDS = (
    "BuiltinTag",
    "CoreAccount",
    "CoreAccountGroup",
    "CoreAccountRole",
    "CoreIPAddressPool",
    "CoreIPPrefixPool",
    "CoreNumberPool",
    "CoreObjectPermission",
    "CoreStandardGroup",
    "InfraAutonomousSystem",
    "InfraBGPPeerGroup",
    "InfraBackBoneService",
    "InfraDevice",
    "InfraMlagDomain",
    "InfraPlatform",
    "InfraVLAN",
    "IpamIPAddress",
    "IpamIPPrefix",
    "LocationContinent",
    "LocationCountry",
    "LocationSite",
    "OrganizationManufacturer",
    "OrganizationProvider",
    "OrganizationTenant",
    "ProfileInfraInterfaceL3",
    "TemplateInfraFrontPatchPanelInterface",
    "TemplateInfraPatchPanel",
)

# Counts probed on every non-default branch (the scenario branches): the
# scenarios add/delete circuits, IPs and platforms relative to main.
SCENARIO_BRANCH_KINDS = (
    "InfraCircuit",
    "InfraCircuitEndpoint",
    "InfraDevice",
    "InfraInterfaceL3",
    "InfraPlatform",
    "IpamIPAddress",
)

# All list queries page with an explicit high limit; the demo dataset tops out
# around 510 nodes for the biggest kind (InfraInterfaceL2).
_GQL_LIMIT = 2000


async def _safe[T](fn: Callable[[], Awaitable[T]]) -> T | str:
    try:
        return await fn()
    except Exception as exc:  # capture per-entry, never kill the whole dump
        return f"ERROR: {type(exc).__name__}: {exc}"


async def _branches(client: InfrahubClient) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "name": branch.name,
                "description": branch.description,
                "sync_with_git": branch.sync_with_git,
                "is_default": branch.is_default,
            }
            for branch in (await client.branch.all()).values()
        ),
        key=operator.itemgetter("name"),
    )


async def _counts(client: InfrahubClient) -> dict[str, Any]:
    kinds = sorted(str(kind) for kind in await client.schema.all())
    return {kind: await _safe(lambda kind=kind: client.count(kind=kind)) for kind in kinds}


async def _names(client: InfrahubClient) -> dict[str, Any]:
    async def labels(kind: str) -> list[str]:
        return sorted(str(node.display_label) for node in await client.all(kind=kind, limit=_GQL_LIMIT))

    return {kind: await _safe(lambda kind=kind: labels(kind)) for kind in NAMED_KINDS}


async def _device_interface_counts(client: InfrahubClient) -> dict[str, int]:
    response = await client.execute_graphql(
        query="""
        query DeviceInterfaceCounts {
            InfraDevice(limit: 2000) {
                edges { node { name { value } interfaces { count } } }
            }
        }
        """
    )
    return {
        edge["node"]["name"]["value"]: edge["node"]["interfaces"]["count"] for edge in response["InfraDevice"]["edges"]
    }


async def _site_device_counts(client: InfrahubClient) -> dict[str, int]:
    response = await client.execute_graphql(
        query="""
        query SiteDeviceCounts {
            InfraDevice(limit: 2000) {
                edges { node { site { node { name { value } } } } }
            }
        }
        """
    )
    counts: dict[str, int] = {}
    for edge in response["InfraDevice"]["edges"]:
        site = (edge["node"]["site"] or {}).get("node")
        name = site["name"]["value"] if site else "<no-site>"
        counts[name] = counts.get(name, 0) + 1
    return counts


async def _group_member_counts(client: InfrahubClient) -> dict[str, int]:
    response = await client.execute_graphql(
        query="""
        query GroupMemberCounts {
            CoreGroup(limit: 2000) {
                edges { node { name { value } members { count } } }
            }
        }
        """
    )
    return {edge["node"]["name"]["value"]: edge["node"]["members"]["count"] for edge in response["CoreGroup"]["edges"]}


async def _bgp_session_types(client: InfrahubClient) -> dict[str, Any]:
    return {
        session_type: await _safe(
            lambda session_type=session_type: client.count(kind="InfraBGPSession", type__value=session_type)
        )
        for session_type in ("EXTERNAL", "INTERNAL")
    }


async def _circuit_roles(client: InfrahubClient) -> dict[str, Any]:
    return {
        role: await _safe(lambda role=role: client.count(kind="InfraCircuit", role__value=role))
        for role in ("upstream", "peering", "backbone")
    }


async def _cabling(client: InfrahubClient) -> dict[str, Any]:
    """Interface-to-interface connected_endpoint pairs + circuit-endpoint link counts."""
    interface_pairs: set[tuple[str, str]] = set()
    circuit_links = 0
    for kind in ("InfraInterfaceL3", "InfraInterfaceL2"):
        query_template = """
            query Cabling__KIND__ {
                __KIND__(limit: 2000) {
                    edges { node {
                        name { value }
                        device { node { name { value } } }
                        connected_endpoint { node {
                            __typename
                            ... on InfraInterfaceL3 { name { value } device { node { name { value } } } }
                            ... on InfraInterfaceL2 { name { value } device { node { name { value } } } }
                        } }
                    } }
                }
            }
            """
        response = await client.execute_graphql(query=query_template.replace("__KIND__", kind))
        for edge in response[kind]["edges"]:
            node = edge["node"]
            peer = (node["connected_endpoint"] or {}).get("node")
            if not peer:
                continue
            if peer["__typename"] == "InfraCircuitEndpoint":
                circuit_links += 1
                continue
            local = f"{node['device']['node']['name']['value']}:{node['name']['value']}"
            remote = f"{peer['device']['node']['name']['value']}:{peer['name']['value']}"
            interface_pairs.add(tuple(sorted((local, remote))))
    return {
        "interface_pairs": sorted(" <-> ".join(pair) for pair in interface_pairs),
        "interface_to_circuit_endpoint_links": circuit_links,
    }


async def _scenario_branches(client: InfrahubClient) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for branch in (await client.branch.all()).values():
        if branch.is_default:
            continue
        result[branch.name] = {
            kind: await _safe(lambda kind=kind, name=branch.name: client.count(kind=kind, branch=name))
            for kind in SCENARIO_BRANCH_KINDS
        }
    return result


async def build_parity_dump(client: InfrahubClient) -> dict[str, Any]:
    return {
        "branches": await _safe(lambda: _branches(client)),
        "counts": await _safe(lambda: _counts(client)),
        "names": await _safe(lambda: _names(client)),
        "topology": {
            "device_interface_counts": await _safe(lambda: _device_interface_counts(client)),
            "site_device_counts": await _safe(lambda: _site_device_counts(client)),
            "group_member_counts": await _safe(lambda: _group_member_counts(client)),
            "bgp_session_types": await _safe(lambda: _bgp_session_types(client)),
            "circuit_roles": await _safe(lambda: _circuit_roles(client)),
            "cabling": await _safe(lambda: _cabling(client)),
        },
        "scenario_branches": await _safe(lambda: _scenario_branches(client)),
    }
