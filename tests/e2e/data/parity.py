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
    from collections.abc import Callable

    from infrahub_sdk import InfrahubClientSync

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


def _safe[T](fn: Callable[[], T]) -> T | str:
    try:
        return fn()
    except Exception as exc:  # capture per-entry, never kill the whole dump
        return f"ERROR: {type(exc).__name__}: {exc}"


def _branches(client: InfrahubClientSync) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "name": branch.name,
                "description": branch.description,
                "sync_with_git": branch.sync_with_git,
                "is_default": branch.is_default,
            }
            for branch in client.branch.all().values()
        ),
        key=operator.itemgetter("name"),
    )


def _counts(client: InfrahubClientSync) -> dict[str, Any]:
    kinds = sorted(str(kind) for kind in client.schema.all())
    return {kind: _safe(lambda kind=kind: client.count(kind=kind)) for kind in kinds}


def _names(client: InfrahubClientSync) -> dict[str, Any]:
    def labels(kind: str) -> list[str]:
        return sorted(str(node.display_label) for node in client.all(kind=kind, limit=_GQL_LIMIT))

    return {kind: _safe(lambda kind=kind: labels(kind)) for kind in NAMED_KINDS}


def _device_interface_counts(client: InfrahubClientSync) -> dict[str, int]:
    response = client.execute_graphql(
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


def _site_device_counts(client: InfrahubClientSync) -> dict[str, int]:
    response = client.execute_graphql(
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


def _group_member_counts(client: InfrahubClientSync) -> dict[str, int]:
    response = client.execute_graphql(
        query="""
        query GroupMemberCounts {
            CoreGroup(limit: 2000) {
                edges { node { name { value } members { count } } }
            }
        }
        """
    )
    return {edge["node"]["name"]["value"]: edge["node"]["members"]["count"] for edge in response["CoreGroup"]["edges"]}


def _bgp_session_types(client: InfrahubClientSync) -> dict[str, Any]:
    return {
        session_type: _safe(
            lambda session_type=session_type: client.count(kind="InfraBGPSession", type__value=session_type)
        )
        for session_type in ("EXTERNAL", "INTERNAL")
    }


def _circuit_roles(client: InfrahubClientSync) -> dict[str, Any]:
    return {
        role: _safe(lambda role=role: client.count(kind="InfraCircuit", role__value=role))
        for role in ("upstream", "peering", "backbone")
    }


def _cabling(client: InfrahubClientSync) -> dict[str, Any]:
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
        response = client.execute_graphql(query=query_template.replace("__KIND__", kind))
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


def _scenario_branches(client: InfrahubClientSync) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for branch in client.branch.all().values():
        if branch.is_default:
            continue
        result[branch.name] = {
            kind: _safe(lambda kind=kind, name=branch.name: client.count(kind=kind, branch=name))
            for kind in SCENARIO_BRANCH_KINDS
        }
    return result


def build_parity_dump(client: InfrahubClientSync) -> dict[str, Any]:
    return {
        "branches": _safe(lambda: _branches(client)),
        "counts": _safe(lambda: _counts(client)),
        "names": _safe(lambda: _names(client)),
        "topology": {
            "device_interface_counts": _safe(lambda: _device_interface_counts(client)),
            "site_device_counts": _safe(lambda: _site_device_counts(client)),
            "group_member_counts": _safe(lambda: _group_member_counts(client)),
            "bgp_session_types": _safe(lambda: _bgp_session_types(client)),
            "circuit_roles": _safe(lambda: _circuit_roles(client)),
            "cabling": _safe(lambda: _cabling(client)),
        },
        "scenario_branches": _safe(lambda: _scenario_branches(client)),
    }
